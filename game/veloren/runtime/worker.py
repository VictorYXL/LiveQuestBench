"""Private VelorenBench runtime reuse, isolated from public Agent interfaces."""

import asyncio
from collections import deque
from contextlib import AsyncExitStack, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback
from uuid import uuid4

from scripts.rpg_benchmark import runtime, setup
from scripts.rpg_benchmark.native import Journal, NativeBridge, NativeConfig, NativeRefusal
from scripts.rpg_benchmark.renderer import RendererBridge

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from game.veloren.fixture import initialize_fixture, recipe_observation, validate_fixture, verify_player
from game.veloren.runtime.server import fixture_server


async def protect_administrator(admin: NativeBridge) -> dict:
    await setup.command(admin, "buff", "invulnerability", 1, 3600)
    return await setup.wait_observation(
        admin,
        lambda row: any(buff.get("kind") == "Invulnerability" for buff in row["survival"]["buffs"]),
        "setup administrator-only invulnerability",
    )


class LocalRenderer(RendererBridge):
    async def envelope(self, request: dict, *, origin: str, timeout: float | None = 60) -> dict:
        # Public steps retain native tick bounds and are cancelled at the Episode deadline.
        # Client updates are not guaranteed to run at 60 Hz.
        return await super().envelope(
            request, origin=origin,
            timeout=None if origin == "agent" and request["cmd"] == "step" else timeout,
        )

    async def start(self) -> None:
        self.ready = asyncio.get_running_loop().create_future()
        self.renderer_ready = asyncio.get_running_loop().create_future()
        settings = self.out / "renderer-config"
        settings.mkdir()
        (settings / "settings.ron").write_text(
            '(show_disclaimer:false,networking:(use_srv:false,use_quic:false,enable_discord_integration:false),'
            'audio:(output:Off),graphics:(terrain_view_distance:4,entity_view_distance:4,lod_distance:0,'
            'max_fps:Max(30),max_background_fps:Max(30),window:(size:(960,540),maximised:false),'
            'fullscreen:(enabled:false),render_mode:(shadow:None,cloud:Minimal,bloom:Off,profiler_enabled:false)),)\n'
        )
        self.stderr = (self.out / "renderer.log").open("x")
        env = os.environ | {
            "HOME": str(self.out / "home"), "VELOREN_ASSETS": self.renderer["paths"]["assets"],
            "VELOREN_SESSION_ID": self.name, "VOXYGEN_CONFIG": str(settings),
            "VELOREN_USERDATA": str(self.out / "renderer-userdata"), "WGPU_BACKEND": "vulkan",
            "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
            "LIVEQUEST_DISABLE_NATIVE_PROTECTION": "1",
            "LIVEQUEST_ROUTE_EVIDENCE": "1" if getattr(self, "route_evidence", False) else "0",
        }
        Path(env["HOME"]).mkdir(exist_ok=True)
        self.process = await asyncio.create_subprocess_exec(
            self.renderer["paths"]["executable"], "--server", f"127.0.0.1:{self.port}",
            "--client-type", "game", "--agent-bridge", "--agent-frame-dir", str(self.frames),
            "--agent-observation", "hybrid", "--agent-offline-user", self.name,
            "--agent-character", self.name, "--agent-create-character",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=self.stderr, env=env, limit=16 * 1024 * 1024,
        )
        from scripts.rpg_benchmark.lifecycle import process_start_ticks
        self.start_ticks = process_start_ticks(self.process.pid)
        self.reader_task = asyncio.create_task(self._read())
        await asyncio.wait_for(asyncio.shield(self.ready), 120)
        await asyncio.wait_for(asyncio.shield(self.renderer_ready), 120)
        if self.renderer_ready.result()["data"]["same_client"] is not True:
            raise RuntimeError("Renderer is not the controlled native player")


class Session:
    def __init__(self, config: dict, output: Path, track: str, fixture: dict,
                 team_role: str | None = None, attachment: dict | None = None):
        self.config, self.output, self.track, self.fixture = config, output, track, validate_fixture(fixture)
        self.stack = AsyncExitStack()
        self.started = False
        self.running = False
        self.record = {"username": "Admin" + uuid4().hex[:10]}
        self.team_role, self.attachment = team_role, attachment
        self.oracle_output = Path(attachment["output"]) if attachment else output
        if attachment:
            self.record["username"] = attachment["username"]
        self.chat_after_seq = 0
        self.chat_history = deque(maxlen=100)
        self.chat_history_truncated = False

    async def start(self) -> dict:
        if self.started:
            raise RuntimeError("Session is single-use")
        self.started = True
        cfg = self.config
        if cfg.get("native_protection") != "disabled by explicit renderer launch environment":
            raise ValueError("Prepared runtime lacks the native-protection opt-out patch; rerun Veloren setup")
        if self.fixture.get("motion_evidence") and cfg.get("motion_evidence") != "native-client-motion/1":
            raise ValueError("Fixture requires passive native motion evidence; rerun Veloren setup")
        if self.fixture.get("glide_evidence") and cfg.get("glide_evidence") != "native-client-glide/1":
            raise ValueError("Fixture requires passive native glide evidence; rerun Veloren setup")
        if self.fixture.get("route_evidence") and cfg.get("route_evidence") != "native-client-route/2":
            raise ValueError("Fixture requires passive native route evidence; rerun Veloren setup")
        if self.fixture.get("pickup_evidence") and cfg.get("pickup_evidence") != "native-server-pickups/1":
            raise ValueError("Fixture requires passive native original-supply evidence")
        if "sword_skill_points" in self.fixture and cfg.get("auxiliary_input") != "native-client-auxiliary/1":
            raise ValueError("Skill fixture requires bounded native auxiliary input; rerun Veloren setup")
        for path, digest in cfg["sha256"].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Prepared runtime changed: {path}")
        selected = runtime.load_runtime(Path(cfg["upstream_runtime"]), cfg["upstream_sha256"], backend="renderer")
        from game.veloren.runtime.server_extension import select_server
        server = select_server(cfg, Path(selected["renderer"]["paths"]["server"]))
        renderer = selected["renderer"]
        renderer["paths"]["executable"] = cfg["renderer"]
        paths = renderer["paths"]
        native = NativeConfig(
            server=server, bridge=Path(selected["renderer_fixture_helper"]["executable"]),
            assets=Path(paths["assets"]), root=Path(paths["source_root"]),
            seed=self.fixture["world_seed"], small_world=False,
        )
        journal = Journal(self.output / "native.jsonl")
        self.stack.callback(journal.close)
        if self.attachment:
            port, userdata = self.attachment["port"], Path(self.attachment["userdata"])
            self.record["world_fixture"] = self.attachment["world_fixture"]
        else:
            port, userdata = await self.stack.enter_async_context(
                fixture_server(self.output, self.record, native, self.fixture))
        from game.veloren.runtime.startup import start_setup_bridge

        administrator = await self.stack.enter_async_context(AsyncExitStack())
        self.setup_bridge_factory = lambda directory: NativeBridge(
            directory, self.record["username"], port, userdata, journal, native,
        )
        admin = await start_setup_bridge(
            self.setup_bridge_factory,
            self.output, administrator, reconnect=bool(self.attachment),
        )
        protected = await protect_administrator(admin)
        administrator_uid = protected["self_identity"]["uid"]
        self.record["setup_admin_protection"] = protected["survival"]["buffs"]
        os.environ["LIVEQUEST_PHYSICAL_INPUT"] = "1" if self.track == "visual_motor" else "0"
        self.actor = LocalRenderer(
            self.output, self.team_role or "Player" + uuid4().hex[:10], port, userdata, journal, native,
            renderer=renderer, frames=self.output / "frames",
        )
        self.stack.push_async_callback(self.actor.close)
        self.actor.route_evidence = self.fixture.get("route_evidence", False)
        await self.actor.start()
        initialized = await initialize_fixture(
            admin, self.actor, self.fixture, shared_world=bool(self.attachment),
            defer_encounters=bool(self.team_role and self.fixture.get("peer_group") and not self.attachment),
            defer_supplies=bool(self.team_role and not self.attachment),
        )
        self.initialized = initialized
        self.setup_administrator = (admin, administrator, administrator_uid)
        if not any(supply["player_target"] is None for supply in initialized["supplies"]):
            await self.finish_setup(finalize_encounters=False, finalize_supplies=False)
        self.record["actor"] = self.actor.ready.result()
        from game.veloren.runtime.records import write_fixture_record
        write_fixture_record(self.output, initialized, self.record["world_fixture"])
        return {"renderer_pid": self.actor.process.pid, "actor": self.actor.ready.result(),
                "runtime": cfg, "display": os.environ["DISPLAY"],
                "shared_world": {"port": port, "userdata": str(userdata), "output": str(self.oracle_output),
                                 "username": self.record["username"], "world_fixture": self.record["world_fixture"]}}

    async def reconnect_setup_administrator(self) -> None:
        from game.veloren.runtime.startup import start_setup_bridge

        administrator = await self.stack.enter_async_context(AsyncExitStack())
        admin = await start_setup_bridge(
            self.setup_bridge_factory, self.output / "deferred-setup", administrator, reconnect=True,
        )
        protected = await protect_administrator(admin)
        self.setup_administrator = (admin, administrator, protected["self_identity"]["uid"])

    async def encounter_binding(self, actor, uid: int) -> dict:
        from game.veloren.runtime.journal import snapshot_binding

        if self.running or actor is not self.actor:
            raise RuntimeError("Encounter binding requires this session's setup actor")
        deadline = asyncio.timeout(10)
        try:
            async with deadline:
                while True:
                    binding = await asyncio.to_thread(
                        snapshot_binding, self.oracle_output / "private-native-oracle.ndjson",
                        self.oracle_output.name, uid, prefix=getattr(self, "snapshot_prefix", None),
                    )
                    if binding is not None:
                        return binding
                    await asyncio.sleep(.1)
        except TimeoutError as error:
            if not deadline.expired():
                raise
            raise RuntimeError(f"private native UID/entity binding unavailable: {uid}") from error

    async def finish_setup(self, *, finalize_encounters: bool = True, finalize_supplies: bool = True) -> None:
        initialized = self.initialized
        if initialized.get("encounters_pending") and finalize_encounters:
            if self.running or not getattr(self, "peer_group_ready", False):
                raise RuntimeError("Peer encounters require a verified Group before gameplay")
        if initialized.get("supplies_pending") and finalize_supplies:
            if self.running or not getattr(self, "team_ready", False):
                raise RuntimeError("Original team supplies require all peers ready before gameplay")
        if (initialized.get("encounters_pending") and finalize_encounters
                or initialized.get("supplies_pending") and finalize_supplies):
            if getattr(self, "setup_administrator", None) is None:
                await self.reconnect_setup_administrator()
        pending = getattr(self, "setup_administrator", None)
        if pending is None:
            return
        from game.veloren.fixture import observe_remote_supplies, verify_aged_supplies

        admin, administrator, administrator_uid = pending
        if initialized.get("supplies_pending") and finalize_supplies:
            from game.veloren.fixture import bind_supplies, initialize_supplies
            initialized["supplies"] = await initialize_supplies(admin, self.fixture["supplies"])
            opening = await self.actor.request("observe", origin="private-validation")
            bind_supplies(initialized["supplies"], opening)
            initialized["supplies_pending"] = False
        if initialized.get("encounters_pending") and finalize_encounters:
            from game.veloren.fixture import initialize_encounters
            initialized.update(await initialize_encounters(
                admin, self.actor, self.fixture, initialized.get("contract"),
                binding_reader=self.encounter_binding,
            ))
            initialized["encounters_pending"] = False
        await observe_remote_supplies(admin, initialized["supplies"])
        await administrator.aclose()
        opening = await setup.wait_observation(
            self.actor,
            lambda row: all(entry["uid"] != administrator_uid for entry in row["nearby_entities"]),
            "fixture administrator disconnected and absent",
        )
        opening = await recipe_observation(self.actor, self.fixture, opening)
        verify_player(self.fixture, opening)
        if initialized.get("merchant") is not None:
            from game.veloren.settlement import verify_merchant
            verify_merchant(opening, initialized["merchant"])
        verify_aged_supplies(initialized, opening)
        initialized["opening"] = opening
        initialized["administrator_retirement"] = {
            "uid": administrator_uid, "confirmed_absent": True,
            "returncode": admin.process.returncode, "cleanup": admin.cleanup,
        }
        self.record["administrator_retirement"] = initialized["administrator_retirement"]
        self.setup_administrator = None
        from game.veloren.runtime.records import write_fixture_record
        write_fixture_record(self.output, initialized, self.record["world_fixture"])

    async def frame_fence(self) -> dict:
        current = await self.actor.request("observe", origin="lifecycle")
        return {"schema_version": "1.0", "expected_session_id": current["session_id"],
                "actor": current["control_actor"]}

    async def physical(self, enabled: bool) -> dict:
        return await self.actor.request(
            "physical_input", {**await self.frame_fence(), "enabled": enabled}, origin="lifecycle",
        )

    async def dispatch(self, operation: str, args: dict) -> dict:
        if operation == "start":
            return await self.start()
        if operation == "setup_peer_group":
            if self.running or not self.team_role or not self.fixture.get("peer_group"):
                raise PermissionError("Native Group setup is only available before declared peer play")
            await self.finish_setup(finalize_encounters=False, finalize_supplies=False)
            mode = args["mode"]
            if mode == "identity":
                row = await self.actor.request("observe", origin="setup")
                return {"uid": row["self_identity"]["uid"], "alias": self.actor.name}
            if mode == "invite":
                await setup.action(self.actor, "social_action", operation="invite_group",
                                   target_uid=args["uid"], target_alias=args["alias"])
            elif mode == "accept":
                await setup.wait_observation(
                    self.actor, lambda row: bool(row["social_and_trade"]["incoming_invite"]),
                    "peer's native Group invitation",
                )
                await setup.action(self.actor, "social_action", operation="respond_accept",
                                   inviter_uid=args["uid"], invite_kind="Group")
            elif mode == "verify":
                await setup.wait_observation(self.actor, lambda row: any(
                    entity["uid"] == args["uid"] and entity.get("same_native_group") is True
                    for entity in row["nearby_entities"]), "native peer Group membership")
                self.peer_group_ready = True
                if self.fixture.get("encounters"):
                    from game.veloren.runtime.journal import snapshot_rows
                    # Validate the long construction prefix before the enemy exists.
                    # Both workers then scan only the append-only suffix at admission.
                    self.snapshot_prefix = {}
                    await asyncio.to_thread(
                        snapshot_rows, self.oracle_output / "private-native-oracle.ndjson",
                        self.oracle_output.name, prepare_prefix=self.snapshot_prefix,
                    )
            else:
                raise ValueError("Unsupported Group setup operation")
            return {"native_group_setup": mode}
        if operation == "setup_team_ready":
            if self.running or not self.team_role or args:
                raise PermissionError("Team readiness is only available before declared peer play")
            self.team_ready = True
            return {"team_ready": True}
        if operation == "begin":
            await self.finish_setup()
            if self.team_role:
                batch = await self.actor.request("events", {"after_seq": 0, "limit": 1}, origin="lifecycle")
                self.chat_after_seq = batch["next_seq"] - 1
            if self.track == "visual_motor":
                await self.physical(True)
            self.running = True
            return {"running": True}
        if operation == "end":
            self.running = False
            if self.track == "visual_motor":
                await self.physical(False)
            await setup.action(self.actor, "stop", origin="cleanup", require_completed=True)
            return {"running": False}
        if operation == "snapshot":
            if self.running:
                raise RuntimeError("Snapshot requires a closed public gate")
            await self.finish_setup()
            observation = await recipe_observation(self.actor, self.fixture)
            from game.veloren.evaluators.deaths import death_snapshot
            from game.veloren.runtime.journal import snapshot_rows
            registry = getattr(self, "death_registry", None)
            rows = await asyncio.to_thread(
                snapshot_rows,
                self.oracle_output / "private-native-oracle.ndjson", self.oracle_output.name,
                after_sequence=registry["opening_sequence"] if registry is not None else None,
                encounters=bool(self.initialized["encounters"]),
                contracts=self.initialized.get("contract") is not None,
                equipment_uid=observation["self_identity"]["uid"],
                pickups=self.fixture.get("pickup_evidence", False),
                prefix=getattr(self, "snapshot_prefix", None),
            )
            observation["private_death_evidence"] = death_snapshot(
                rows, observation["self_identity"], registry,
            )
            self.death_registry = observation["private_death_evidence"]["registry"]
            if self.fixture.get("pickup_evidence") and not self.attachment:
                from game.veloren.evaluators.pickups import pickup_snapshot
                evidence = pickup_snapshot(
                    rows, self.initialized["supplies"], self.death_registry,
                    observation["survival"]["buff_clock"]["now"], getattr(self, "pickup_registry", None),
                )
                observation["private_pickup_evidence"] = evidence
                self.pickup_registry = evidence["registry"]
            if not self.attachment and not hasattr(self, "supplies_opening"):
                from game.veloren.fixture import verify_aged_supplies
                verify_aged_supplies(self.initialized, observation)
                self.supplies_opening = True
            if self.initialized.get("merchant") is not None and not hasattr(self, "merchant_opening"):
                from game.veloren.settlement import verify_merchant
                verify_merchant(observation, self.initialized["merchant"])
                self.merchant_opening = True
            if self.fixture.get("route_evidence"):
                observation["private_route_evidence"] = await self.actor.request(
                    "route_evidence", await self.frame_fence(), origin="private-validation",
                )
            if self.fixture.get("motion_evidence") or self.fixture.get("glide_evidence"):
                observation["private_motion_evidence"] = await self.actor.request(
                    "glide_evidence" if self.fixture.get("glide_evidence") else "motion_evidence",
                    await self.frame_fence(), origin="private-validation",
                )
            if self.initialized["encounters"]:
                targets = self.initialized["encounters"]
                if not hasattr(self, "encounter_registry"):
                    verify_player(self.fixture, observation)
                    from game.veloren.fixture import verify_encounter_opening
                    verify_encounter_opening(targets, observation, rows)
                    current = {entry["uid"]: entry for entry in observation["nearby_entities"]}
                    self.encounter_registry = {
                        "run_id": self.output.name, "nonce": rows[0]["data"]["nonce"],
                        "opening_sequence": rows[-1]["sequence"],
                        "source": self.initialized["source_binding"],
                        "targets": [{"role": target["role"], "asset": target["asset"],
                                     "binding": target["binding"]} for target in targets],
                    }
                    if self.initialized.get("companion") is not None:
                        companion = self.initialized["companion"]
                        pet = current.get(companion["binding"]["uid"])
                        if (pet is None or pet["control_target"] != companion["player_target"]
                                or pet["companion"]["owned_by_actor"] is not True
                                or pet["same_native_group"] is not True
                                or pet["health"]["current"] != companion.get("initial_health", companion["binding"]["maximum_health"])
                                or pet["health"]["dead"]):
                            raise RuntimeError("Owned companion unavailable or injured before measured play")
                        self.encounter_registry["companion"] = {
                            key: companion[key] for key in ("binding", "player_target", "initial_health")
                            if key in companion
                        }
                equipment_samples = []
                previous_equipment = self.encounter_registry["source"]["equipment"]
                for row in rows:
                    if (row["sequence"] <= self.encounter_registry["opening_sequence"]
                            or row["event"] != "combat_entity_bindings"):
                        continue
                    for binding in row["data"]["bindings"]:
                        if (binding["uid"] == self.encounter_registry["source"]["uid"]
                                and binding["equipment"] != previous_equipment):
                            equipment_samples.append({
                                "sequence": row["sequence"], "uid": binding["uid"],
                                "server_entity": binding["server_entity"], "equipment": binding["equipment"],
                            })
                            previous_equipment = binding["equipment"]
                observation["private_encounter_evidence"] = {
                    "schema": "livequest-encounter/1", "registry": self.encounter_registry,
                    "through_sequence": rows[-1]["sequence"],
                    "equipment_samples": equipment_samples,
                    "events": [row for row in rows if row["sequence"] > self.encounter_registry["opening_sequence"]
                               and row["event"] in ("health_effect_applied", "native_entity_death",
                                                    "attack_health_effect_queued")],
                }
                if "companion" in self.encounter_registry:
                    bindings = next(row["data"]["bindings"] for row in reversed(rows)
                                    if row["event"] == "combat_entity_bindings")
                    observation["private_encounter_evidence"]["companion_binding"] = next(
                        (row for row in bindings
                         if row["uid"] == self.encounter_registry["companion"]["binding"]["uid"]), None,
                    )
                if self.initialized.get("contract") is not None:
                    from game.veloren.contracts import contract_registry, contract_snapshot
                    if not hasattr(self, "contract_registry"):
                        self.contract_registry = contract_registry(self.initialized["contract"], observation, rows)
                        self.contract_opening = dict(observation)
                    observation["private_contract_evidence"] = contract_snapshot(
                        self.contract_registry, self.contract_opening, observation, rows,
                    )
            return observation
        if operation == "inspect_frame":
            return await self.actor.request("frame", await self.frame_fence(), origin="private-validation")
        if not self.running:
            raise RuntimeError("Public native operation outside running boundary")
        if operation in ("chat_send", "chat_inbox"):
            if self.track != "structured_tool" or not self.team_role:
                raise PermissionError("Native chat RPC requires a structured team participant")
            if operation == "chat_send":
                action = ({"action_type": "private_chat", "recipient": args["recipient"]}
                          if args.get("recipient") else {"action_type": "chat_channel", "channel": "world"})
                return await setup.action(self.actor, origin="agent", require_completed=False,
                                          **action, message=args["message"])
            while True:
                batch = await self.actor.request(
                    "events", {"after_seq": self.chat_after_seq, "limit": 256}, origin="agent")
                self.chat_history_truncated |= batch["truncated"]
                for event in batch["events"]:
                    self.chat_after_seq = event["seq"]
                    if event["event"] == "chat":
                        self.chat_history_truncated |= len(self.chat_history) == self.chat_history.maxlen
                        self.chat_history.append(event)
                if not batch["has_more"]:
                    break
            return {"messages": list(self.chat_history), "history_truncated": self.chat_history_truncated,
                    "through_seq": self.chat_after_seq, "history_limit": 100,
                    "scope": "own_native_received_chat"}
        if operation == "observe":
            return await self.actor.request("observe", origin="agent")
        if operation == "action":
            if self.track != "structured_tool":
                raise PermissionError("VM cannot invoke native skills")
            if args.get("action_type") not in (
                "move_forward", "move_backward", "move_left", "move_right",
                "turn", "jump", "wall_jump", "pickup", "use_item", "craft", "equip",
                "look_at", "attack_primary", "attack_secondary", "toggle_wield", "block", "roll", "stop",
                "aimed_attack", "glide", "context_interact", "social_action", "dialogue_action", "trade_action",
                "unlock_skill", "configure_auxiliary_ability", "attack_auxiliary",
                "companion_action", "respawn",
            ):
                raise PermissionError("Native action is not in the fixed public skill set")
            rpg_actions = {
                "context_interact": ("talk",), "social_action": ("invite_trade", "respond_accept", "respond_decline"),
                "dialogue_action": ("ack", "respond"),
                "trade_action": ("add_item", "remove_item", "accept", "decline"),
                "companion_action": ("pet_stay",),
            }
            if args["action_type"] in rpg_actions and args.get("operation") not in rpg_actions[args["action_type"]]:
                raise PermissionError("Native RPG operation is not in the fixed public skill set")
            if (args["action_type"] == "social_action" and args.get("operation", "").startswith("respond_")
                    and (not self.team_role or args.get("invite_kind") != "Trade")):
                raise PermissionError("Public invitation responses require a peer Trade invitation")
            try:
                if args["action_type"] == "glide":
                    result = await setup.action(
                        self.actor, origin="agent", require_completed=False,
                        action_type="character_action", kind="glide", enabled=args["enabled"],
                    )
                    return {**result, "action_type": "glide"}
                if args["action_type"] == "aimed_attack":
                    aimed = await setup.action(
                        self.actor, origin="agent", require_completed=False, action_type="look_at",
                        position=[args[axis] for axis in ("x", "y", "z")],
                    )
                    if aimed["status"] != "completed":
                        return {**aimed, "action_type": "aimed_attack"}
                    if not self.running:
                        return {"action_type": "aimed_attack", "status": "cancelled",
                                "detail": {"code": "public_gate_closed_before_attack"}}
                    struck = await setup.action(
                        self.actor, origin="agent", require_completed=False, action_type="attack_primary",
                        duration_ticks=args["duration_ticks"],
                    )
                    return {**struck, "action_type": "aimed_attack", "started_tick": aimed["started_tick"]}
                return await setup.action(self.actor, origin="agent", require_completed=False, **args)
            except NativeRefusal as error:
                expected = {
                    ("glide", "glider_not_equipped", "no equipped glider"),
                    ("pickup", "invalid_action", "no pickable item within range"),
                    ("pickup", "pickup_send_rejected",
                     "local client does not send pickup while dead; not a server refusal"),
                    ("use_item", "invalid_action", "inventory slot is empty or unavailable"),
                    ("equip", "invalid_action", "inventory slot is empty"),
                }
                refusal = error.native_error
                rpg_refusals = {
                    "unlock_skill": {"invalid_action", "skill_ineligible", "skill_state_unavailable"},
                    "configure_auxiliary_ability": {"ability_ineligible"},
                    "attack_auxiliary": {"auxiliary_ineligible"},
                    "companion_action": {"actor_unavailable", "companion_target_changed", "pet_not_owned_or_nearby"},
                    "context_interact": {"actor_unavailable", "interaction_target_changed", "interaction_ineligible"},
                    "social_action": {"actor_unavailable", "trade_target_changed", "trade_already_pending",
                                      "invite_unavailable", "invite_changed"},
                    "dialogue_action": {"dialogue_unavailable", "dialogue_changed", "dialogue_sender_changed",
                                        "dialogue_sender_unavailable", "dialogue_response_unknown"},
                    "trade_action": {"actor_unavailable", "no_pending_trade", "trade_identity_or_phase_changed",
                                     "trade_slot_unavailable", "trade_offer_changed"},
                }
                if refusal.get("code") in rpg_refusals.get(args["action_type"], set()):
                    return {"action_type": args["action_type"], "status": "refused", "detail": refusal}
                expected.update({
                    ("dialogue_action", "invalid_action",
                     "dialogue action must match a current statement tag or offered question choice"),
                    ("trade_action", "invalid_action",
                     "trade action fields/phase do not match an offer or accept/decline"),
                })
                if (args["action_type"], refusal.get("code"), refusal.get("message")) not in expected:
                    raise
                return {"action_type": args["action_type"], "status": "refused", "detail": refusal}
        raise ValueError(f"Unknown worker operation: {operation}")

    async def close(self) -> None:
        try:
            await self.stack.aclose()
        finally:
            (self.output / "native-cleanup.json").write_text(json.dumps(self.record, indent=2) + "\n")
            if hasattr(self, "initialized") and not hasattr(self, "authoring_digest"):
                from game.veloren.runtime.records import write_authoring_detail, write_fixture_record
                self.authoring_digest = write_authoring_detail(self.output, self.initialized)
                write_fixture_record(
                    self.output, self.initialized, self.record["world_fixture"], self.authoring_digest,
                )


async def main() -> None:
    config_path, output, track, fixture = sys.argv[1:]
    values = json.loads(Path(fixture).read_text())
    session = Session(json.loads(Path(config_path).read_text()), Path(output), track,
                      values["fixture"] if "team_role" in values else values,
                      values.get("team_role"), values.get("attachment"))
    output_stream = sys.stdout
    pending = set()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop.set)

    async def respond(request):
        try:
            value = await session.dispatch(request["op"], request["arguments"])
            response = {"id": request["id"], "ok": True, "result": value}
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            response = {"id": request["id"], "ok": False,
                        "error": {"type": type(error).__name__, "message": str(error)}}
        output_stream.write(json.dumps(response, allow_nan=False) + "\n")
        output_stream.flush()

    reader = asyncio.StreamReader(limit=16 * 1024 * 1024)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    with redirect_stdout(sys.stderr):
        try:
            while not stop.is_set():
                reading = asyncio.create_task(reader.readline())
                stopping = asyncio.create_task(stop.wait())
                done, _ = await asyncio.wait({reading, stopping}, return_when=asyncio.FIRST_COMPLETED)
                stopping.cancel()
                await asyncio.gather(stopping, return_exceptions=True)
                if reading not in done:
                    reading.cancel()
                    await asyncio.gather(reading, return_exceptions=True)
                    break
                line = reading.result()
                if not line:
                    break
                request = json.loads(line)
                if request["op"] == "close":
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    await session.close()
                    output_stream.write(json.dumps({"id": request["id"], "ok": True, "result": {"closed": True}}) + "\n")
                    output_stream.flush()
                    break
                task = asyncio.create_task(respond(request))
                pending.add(task)
                task.add_done_callback(pending.discard)
        finally:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
