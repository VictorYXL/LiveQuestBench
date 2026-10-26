"""Stateful X11 keyboard/mouse primitives for one explicitly bound window."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
import logging
import threading
import time

from Xlib import X, XK, display, error


KEYS = {key: key for key in "abcdefghijklmnopqrstuvwxyz0123456789"}
KEYS.update({
    "space": "space", "enter": "Return", "escape": "Escape", "tab": "Tab",
    "backspace": "BackSpace", "delete": "Delete", "insert": "Insert",
    "left": "Left", "right": "Right", "up": "Up", "down": "Down",
    "home": "Home", "end": "End", "page_up": "Prior", "page_down": "Next",
    "left_shift": "Shift_L", "right_shift": "Shift_R",
    "left_ctrl": "Control_L", "right_ctrl": "Control_R",
    "slash": "slash", "backslash": "backslash", "comma": "comma", "period": "period",
    "minus": "minus", "equal": "equal", "semicolon": "semicolon", "apostrophe": "apostrophe",
    "left_bracket": "bracketleft", "right_bracket": "bracketright", "grave": "grave",
})
BUTTONS = {"left": 1, "middle": 2, "right": 3}
X_FAILURES = (error.XError, error.DisplayError, error.ConnectionClosedError, OSError)
logger = logging.getLogger(__name__)


class ActionError(RuntimeError):
    """Input was rejected or could not be submitted reliably."""


@dataclass(frozen=True)
class ActionResult:
    operation: str
    started_at_ns: int
    finished_at_ns: int
    applied_delta: tuple[int, int] | None = None


def integer(value: int, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ActionError(f"{name} must be an integer in [{low}, {high}].")
    return value


class WindowActions:
    """Generic XTest backend, not a Minecraft skill/tool layer.

    Successful methods mean X11 accepted input, not that a game consumed it.
    XTest is session-global: focus checks are best-effort, not an isolation boundary.
    Never share an active control session with manual keyboard/mouse use.
    """

    def __init__(self, window_id: int, display_name: str | None = None) -> None:
        integer(window_id, "window_id", 1, 0xFFFFFFFF)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._display = None
        self._held_keys: dict[str, tuple[int, float]] = {}
        self._held_buttons: dict[str, tuple[int, float]] = {}
        self._failure: str | None = None
        try:
            self._display = display.Display(display_name)
            self._display.display.socket.settimeout(2)
            if not self._display.has_extension("XTEST"):
                raise ActionError("XTEST extension is required.")
            if window_id == self._display.screen().root.id:
                raise ActionError("Bind an application window, not the desktop root.")
            self._window = self._display.create_resource_object("window", window_id)
            self._check_target()
            self._thread = threading.Thread(
                target=self._watch, name="window-input-watchdog", daemon=True,
            )
            self._thread.start()
        except (*X_FAILURES, ActionError) as exc:
            if self._display is not None:
                self._display.close()
                self._display = None
            raise ActionError(f"Cannot initialize input: {exc}") from exc

    def __enter__(self) -> WindowActions:
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def _connection(self):
        if self._display is None:
            raise ActionError("Input connection is closed.")
        return self._display

    def _belongs_to_target(self, window) -> bool:
        connection = self._connection()
        for _ in range(32):
            wid = getattr(window, "id", window)
            if wid == self._window.id:
                return True
            if wid in (X.NONE, X.PointerRoot, connection.screen().root.id):
                return False
            window = connection.create_resource_object("window", int(wid)).query_tree().parent
        return False

    def _check_target(self, pointer: bool = False) -> None:
        connection = self._connection()
        if self._window.get_attributes().map_state != X.IsViewable:
            raise ActionError("Target window is not viewable.")
        if not self._belongs_to_target(connection.get_input_focus().focus):
            raise ActionError("Target window lost keyboard focus; input stopped.")
        # Disallow externally held desktop modifiers as well as exposing none ourselves.
        keymap = connection.query_keymap()
        for name in ("Alt_L", "Alt_R", "Super_L", "Super_R", "Meta_L", "Meta_R"):
            code = connection.keysym_to_keycode(XK.string_to_keysym(name))
            if code and keymap[code // 8] & (1 << (code % 8)):
                raise ActionError("External Alt/Super/Meta modifier is held; input stopped.")
        if pointer:
            current = self._window
            position = current.query_pointer()
            geometry = current.get_geometry()
            if not position.same_screen or not (
                0 <= position.win_x < geometry.width and 0 <= position.win_y < geometry.height
            ):
                raise ActionError("Pointer is outside the target window.")
            # Walking from root detects a different window covering the target.
            current = connection.screen().root
            for _ in range(32):
                child = current.query_pointer().child
                if not child:
                    raise ActionError("Pointer does not target the bound window.")
                if child.id == self._window.id:
                    break
                current = child
            else:
                raise ActionError("Cannot resolve pointer target.")

    def check_ready(self) -> None:
        with self._lock:
            if self._failure:
                raise ActionError(self._failure)
            try:
                self._check_target(pointer=bool(self._held_buttons))
            except (*X_FAILURES, ActionError) as exc:
                self._abort(str(exc))
                raise ActionError(self._failure) from exc

    def window_size(self) -> tuple[int, int]:
        with self._lock:
            self.check_ready()
            try:
                geometry = self._window.get_geometry()
                return geometry.width, geometry.height
            except X_FAILURES as exc:
                self._abort(str(exc))
                raise ActionError(self._failure) from exc

    def _release(self) -> list[str]:
        connection = self._connection()
        failures = []
        for held, event_type in (
            (self._held_buttons, X.ButtonRelease), (self._held_keys, X.KeyRelease),
        ):
            for name, (code, _) in list(held.items()):
                try:
                    connection.xtest_fake_input(event_type, code)
                    connection.sync()
                    del held[name]
                except X_FAILURES as exc:
                    failures.append(f"{name}: {exc}")
        return failures

    def _abort(self, reason: str) -> None:
        self._failure = reason
        failures = self._release()
        if failures:
            self._failure += "; release failed: " + "; ".join(failures)
        self._stop.set()

    def _watch(self) -> None:
        while not self._stop.wait(0.05):
            with self._lock:
                try:
                    self._check_target(pointer=bool(self._held_buttons))
                except (*X_FAILURES, ActionError) as exc:
                    self._abort(str(exc))
                    logger.error("Input watchdog stopped the session: %s", self._failure)
                    return

    def _perform(self, operation: str, submit: Callable[[], None],
                 pointer: bool = False) -> ActionResult:
        with self._lock:
            if self._failure:
                raise ActionError(self._failure)
            connection = self._connection()
            started = time.monotonic_ns()
            try:
                self._check_target(pointer=pointer or bool(self._held_buttons))
                submit()
                connection.sync()
            except (*X_FAILURES, ActionError) as exc:
                self._abort(str(exc))
                raise ActionError(self._failure) from exc
            return ActionResult(operation, started, time.monotonic_ns())

    def _keycode(self, key: str) -> int:
        if not isinstance(key, str) or key not in KEYS:
            raise ActionError(f"Unsupported key: {key!r}")
        code = self._connection().keysym_to_keycode(XK.string_to_keysym(KEYS[key]))
        if not code:
            raise ActionError(f"Key unavailable in current X11 keymap: {key}")
        return code

    def key_down(self, key: str) -> ActionResult:
        def submit():
            code = self._keycode(key)
            if key in self._held_keys:
                return
            keymap = self._connection().query_keymap()
            if keymap[code // 8] & (1 << (code % 8)):
                raise ActionError(f"Key {key} is already held outside this executor.")
            self._held_keys[key] = (code, time.monotonic())
            self._connection().xtest_fake_input(X.KeyPress, code)
        return self._perform("key_down", submit)

    def key_up(self, key: str) -> ActionResult:
        def submit():
            self._keycode(key)
            if key in self._held_keys:
                self._connection().xtest_fake_input(X.KeyRelease, self._held_keys[key][0])
                self._connection().sync()
                del self._held_keys[key]
        return self._perform("key_up", submit)

    def mouse_down(self, button: str) -> ActionResult:
        def submit():
            if not isinstance(button, str) or button not in BUTTONS:
                raise ActionError(f"Unsupported button: {button!r}")
            if button in self._held_buttons:
                return
            code = BUTTONS[button]
            if self._window.query_pointer().mask & (1 << (7 + code)):
                raise ActionError(f"Button {button} is already held outside this executor.")
            self._held_buttons[button] = (code, time.monotonic())
            self._connection().xtest_fake_input(X.ButtonPress, code)
        return self._perform("mouse_down", submit, pointer=True)

    def mouse_up(self, button: str) -> ActionResult:
        def submit():
            if not isinstance(button, str) or button not in BUTTONS:
                raise ActionError(f"Unsupported button: {button!r}")
            if button in self._held_buttons:
                self._connection().xtest_fake_input(X.ButtonRelease, self._held_buttons[button][0])
                self._connection().sync()
                del self._held_buttons[button]
        return self._perform("mouse_up", submit)

    def mouse_move_relative(self, dx: int, dy: int) -> ActionResult:
        integer(dx, "dx", -32768, 32767)
        integer(dy, "dy", -32768, 32767)
        applied = (0, 0)

        def submit():
            nonlocal applied
            position = self._window.query_pointer()
            geometry = self._window.get_geometry()
            applied = (
                max(-position.win_x, min(dx, geometry.width - 1 - position.win_x)),
                max(-position.win_y, min(dy, geometry.height - 1 - position.win_y)),
            )
            self._connection().xtest_fake_input(X.MotionNotify, detail=1, x=applied[0], y=applied[1])

        result = self._perform("mouse_move_relative", submit, pointer=True)
        return replace(result, applied_delta=applied)

    def mouse_move_to(self, x: int, y: int) -> ActionResult:
        def submit():
            geometry = self._window.get_geometry()
            integer(x, "x", 0, geometry.width - 1)
            integer(y, "y", 0, geometry.height - 1)
            root = self._connection().screen().root
            position = root.translate_coords(self._window, x, y)
            integer(position.x, "root x", 0, min(32767, root.get_geometry().width - 1))
            integer(position.y, "root y", 0, min(32767, root.get_geometry().height - 1))
            self._connection().xtest_fake_input(
                X.MotionNotify, root=root.id, x=position.x, y=position.y,
            )
            self._connection().sync()
            self._check_target(pointer=True)
        return self._perform("mouse_move_to", submit)

    def mouse_scroll(self, steps: int) -> ActionResult:
        integer(steps, "steps", -20, 20)
        def submit():
            button = 4 if steps > 0 else 5
            for _ in range(abs(steps)):
                self._held_buttons["_wheel"] = (button, time.monotonic())
                self._connection().xtest_fake_input(X.ButtonPress, button)
                self._connection().xtest_fake_input(X.ButtonRelease, button)
                self._connection().sync()
                del self._held_buttons["_wheel"]
        return self._perform("mouse_scroll", submit, pointer=True)

    def release_all(self) -> ActionResult:
        with self._lock:
            started = time.monotonic_ns()
            failures = self._release()
            if failures:
                self._failure = "Release failed: " + "; ".join(failures)
                raise ActionError(self._failure)
            return ActionResult("release_all", started, time.monotonic_ns())

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        with self._lock:
            if self._display is not None:
                try:
                    self.release_all()
                finally:
                    self._display.close()
                    self._display = None
