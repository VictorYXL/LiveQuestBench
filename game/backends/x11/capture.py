"""On-demand application-window capture on X11, without desktop screenshots."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from Xlib.ext.composite import _Update

from PIL import Image
from Xlib import X, display, error
from Xlib.ext import composite


class CaptureError(RuntimeError):
    """A fresh game-window image could not be obtained."""


@dataclass(frozen=True)
class GameWindow:
    window_id: int
    title: str
    width: int
    height: int


@dataclass(frozen=True)
class CapturedFrame:
    frame_id: int
    window_id: int
    capture_started_at_ns: int
    captured_at_ns: int
    image: Image.Image


def decode_image(data: bytes, width: int, height: int, bits_per_pixel: int,
                 scanline_pad: int, byte_order: int,
                 masks: tuple[int, int, int]) -> Image.Image:
    if masks != (0xFF0000, 0x00FF00, 0x0000FF):
        raise CaptureError(f"Unsupported X11 RGB masks: {masks}")
    if bits_per_pixel not in (24, 32) or scanline_pad not in (8, 16, 32):
        raise CaptureError(f"Unsupported X11 pixel layout: {bits_per_pixel}/{scanline_pad}")
    if byte_order not in (X.LSBFirst, X.MSBFirst):
        raise CaptureError(f"Unsupported X11 byte order: {byte_order}")
    stride = ((width * bits_per_pixel + scanline_pad - 1) // scanline_pad) * (scanline_pad // 8)
    if len(data) != stride * height:
        raise CaptureError("Incomplete X11 image payload.")
    mode = {
        (24, X.LSBFirst): "BGR", (24, X.MSBFirst): "RGB",
        (32, X.LSBFirst): "BGRX", (32, X.MSBFirst): "XRGB",
    }[bits_per_pixel, byte_order]
    return Image.frombytes("RGB", (width, height), data, "raw", mode, stride, 1)


class WindowCapture:
    """One synchronous, single-caller X11 capture connection.

    Each capture reads a new window pixmap; no historical frame is cached.
    Timestamps use monotonic_ns and describe readback, not the game's render tick.
    """

    def __init__(self, display_name: str | None = None, *, title_prefix: str,
                 class_tokens: tuple[str, ...] = ()) -> None:
        if not title_prefix:
            raise ValueError("A nonempty window title prefix is required")
        self.title_prefix, self.class_tokens = title_prefix, class_tokens
        self._display = None
        self._frame_id = 0
        try:
            self._display = display.Display(display_name)
            self._display.display.socket.settimeout(5)
            if not self._display.has_extension("Composite"):
                raise CaptureError("XComposite is unavailable; desktop capture is not used as a fallback.")
            version = self._display.composite_query_version()
            if (version.major_version, version.minor_version) < (0, 2):
                raise CaptureError("XComposite >= 0.2 is required.")
        except (error.DisplayError, error.XError, OSError, CaptureError) as exc:
            self.close()
            raise CaptureError(
                f"Cannot open X11 capture: {exc}. Run in your authorized X11 desktop "
                "or provide its DISPLAY and XAUTHORITY. Native Wayland is not supported."
            ) from exc

    def close(self) -> None:
        if self._display is not None:
            self._display.close()
            self._display = None

    def __enter__(self) -> WindowCapture:
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def _connection(self):
        if self._display is None:
            raise CaptureError("Capture connection is closed.")
        return self._display

    def _describe(self, window) -> GameWindow | None:
        classes = window.get_wm_class() or ()
        title_prop = window.get_full_property(
            self._connection().intern_atom("_NET_WM_NAME"), X.AnyPropertyType,
        )
        title = (
            bytes(title_prop.value).decode("utf-8", errors="replace")
            if title_prop is not None and title_prop.format == 8
            else window.get_wm_name() or ""
        )
        if not isinstance(title, str):
            return None
        if not title.startswith(self.title_prefix) or (self.class_tokens and not any(
            token in value.lower() for value in classes for token in self.class_tokens
        )):
            return None
        geometry = window.get_geometry()
        return GameWindow(window.id, title, geometry.width, geometry.height)

    def list_windows(self) -> list[GameWindow]:
        connection = self._connection()
        try:
            root = connection.screen().root
            clients = root.get_full_property(
                connection.intern_atom("_NET_CLIENT_LIST"), X.AnyPropertyType,
            )
            windows = (
                [connection.create_resource_object("window", int(wid)) for wid in clients.value]
                if clients is not None else root.query_tree().children
            )
            result = []
            for window in windows:
                try:
                    description = self._describe(window)
                except error.BadWindow:
                    continue
                if description is not None:
                    result.append(description)
            return result
        except (error.XError, error.ConnectionClosedError, OSError) as exc:
            raise CaptureError(f"Cannot enumerate game windows: {exc}") from exc

    def capture(self, window_id: int | None = None) -> CapturedFrame:
        connection = self._connection()
        if window_id is None:
            windows = self.list_windows()
            if len(windows) != 1:
                raise CaptureError(
                    f"Expected one {self.title_prefix} window, found {len(windows)}. "
                    "Open the game or use --list and select --window-id."
                )
            window_id = windows[0].window_id
        window = connection.create_resource_object("window", window_id)
        pixmap = None
        redirected = False
        try:
            if self._describe(window) is None:
                raise CaptureError("Selected window does not match the configured application.")
            attributes = window.get_attributes()
            geometry = window.get_geometry()
            if attributes.map_state != X.IsViewable:
                raise CaptureError("Game window is unmapped/minimized; restore it before capture.")
            hidden = window.get_full_property(connection.intern_atom("_NET_WM_STATE"), X.AnyPropertyType)
            if hidden is not None and connection.intern_atom("_NET_WM_STATE_HIDDEN") in hidden.value:
                raise CaptureError("Game window is minimized; restore it before capture.")
            if not 0 < geometry.width * geometry.height <= 32_000_000:
                raise CaptureError("Invalid or excessively large game window.")
            started = time.monotonic_ns()
            caught = error.CatchError()
            composite.redirect_window(window, cast("_Update", composite.RedirectAutomatic), onerror=caught)
            connection.sync()
            if caught.get_error() is not None:
                raise CaptureError(f"Cannot redirect game window: {caught.get_error()}")
            redirected = True
            caught = error.CatchError()
            pixmap = composite.name_window_pixmap(window, onerror=caught)
            connection.sync()
            if caught.get_error() is not None:
                raise CaptureError(f"Cannot access game window pixmap: {caught.get_error()}")
            reply = pixmap.get_image(
                geometry.border_width, geometry.border_width,
                geometry.width, geometry.height, X.ZPixmap, 0xFFFFFFFF,
            )
            finished = time.monotonic_ns()
            current = window.get_geometry()
            if (current.width, current.height) != (geometry.width, geometry.height):
                raise CaptureError("Game window resized during capture; request another frame.")
            if window.get_attributes().map_state != X.IsViewable:
                raise CaptureError("Game window became unmapped during capture.")
            formats = connection.display.info.pixmap_formats
            pixel_format = next((item for item in formats if item.depth == geometry.depth), None)
            visual = next((
                item for depth in connection.screen().allowed_depths
                for item in depth.visuals if item.visual_id == attributes.visual
            ), None)
            if reply is None or pixel_format is None or visual is None:
                raise CaptureError("X11 did not return a supported window image format.")
            image = decode_image(
                reply.data, geometry.width, geometry.height, pixel_format.bits_per_pixel,
                pixel_format.scanline_pad, connection.display.info.image_byte_order,
                (visual.red_mask, visual.green_mask, visual.blue_mask),
            )
            self._frame_id += 1
            return CapturedFrame(self._frame_id, window_id, started, finished, image)
        except (error.XError, error.ConnectionClosedError, OSError) as exc:
            raise CaptureError(f"Game capture failed (window may have closed): {exc}") from exc
        finally:
            # BadWindow/BadPixmap during teardown can follow a normal window close.
            try:
                if pixmap is not None:
                    pixmap.free(onerror=error.CatchError(error.BadPixmap))
                if redirected:
                    composite.unredirect_window(
                        window,
                        cast("_Update", composite.RedirectAutomatic), onerror=error.CatchError(error.BadWindow),
                    )
                connection.sync()
            except (error.XError, error.ConnectionClosedError, OSError) as exc:
                raise CaptureError(f"Capture connection failed during cleanup: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--display", help="Authorized X11 display; defaults to DISPLAY.")
    parser.add_argument("--title", required=True, help="Required application window title prefix.")
    parser.add_argument("--list", action="store_true", help="List matching windows without capturing.")
    parser.add_argument("--window-id", type=lambda value: int(value, 0))
    parser.add_argument("--output", type=Path, help="New PNG path; existing files are not overwritten.")
    args = parser.parse_args()
    if not args.list and args.output is None:
        parser.error("--output is required unless --list is used")
    try:
        with WindowCapture(args.display, title_prefix=args.title) as capture:
            if args.list:
                for window in capture.list_windows():
                    print(f"{window.window_id:#x} {window.width}x{window.height} {window.title}")
            else:
                frame = capture.capture(args.window_id)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("xb") as output:
                    frame.image.save(output, format="PNG")
                print(json.dumps({
                    "frame_id": frame.frame_id, "window_id": hex(frame.window_id),
                    "capture_started_at_ns": frame.capture_started_at_ns,
                    "captured_at_ns": frame.captured_at_ns,
                    "width": frame.image.width, "height": frame.image.height,
                    "output": str(args.output),
                }))
    except (CaptureError, error.DisplayError, error.XError, error.ConnectionClosedError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
