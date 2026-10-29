"""Restore only the original courier's declared NBT before public readiness."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import time

import nbtlib

from game.minecraft.evaluators.camel_delivery import original_camel
from game.minecraft.runtime.server import MinecraftServer


class CourierInitializationServer(MinecraftServer):
    def __init__(self, *args, template: Path, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = Path(template)
        self.initialized = False

    async def start(self):
        if self.initialized:
            raise RuntimeError("Courier initialization is allowed only once before readiness")
        _, template = original_camel(self.template)
        selector = '@e[type=minecraft:camel,tag=lq_camel_response,nbt={UUID:' + template["UUID"].snbt() + '},limit=1]'
        expected = nbtlib.parse_nbt(template.snbt())
        expected.pop("id", None)
        record = {
            "schema": "livequest-camel-pre-ready-restoration/1",
            "template": str(self.template), "template_camel_snbt": template.snbt(),
            "template_camel_sha256": hashlib.sha256(template.snbt().encode()).hexdigest(),
            "initialization_only": True, "public_ready_reached": False,
            "normal_dynamics_after_ready": True, "commands": [],
        }
        receipt = self.directory / "courier-startup-restoration.json"

        async def command(text):
            requested_at_ns = time.monotonic_ns()
            feedback = await self.command(text)
            record["commands"].append({"command": text, "feedback": feedback,
                                       "requested_at_ns": requested_at_ns,
                                       "acknowledged_at_ns": time.monotonic_ns()})
            receipt.write_text(json.dumps(record, indent=2) + "\n")
            return feedback

        async def read_camel():
            lines = await command(f"data get entity {selector}")
            marker = " has the following entity data: "
            values = [nbtlib.parse_nbt(line.split(marker, 1)[1]) for line in lines if marker in line]
            if len(values) != 1 or list(values[0]["UUID"]) != list(template["UUID"]):
                raise RuntimeError("The original native courier is unavailable during initialization")
            return values[0]

        try:
            await super().start()
            frozen = await command("tick freeze")
            if not any("The game is frozen" in line for line in frozen):
                raise RuntimeError("Could not freeze the native courier before initialization")
            before = await read_camel()
            record["native_before_snbt"] = before.snbt()
            record["before_capture_boundary"] = "After first native freeze, before any restoration or client connection."
            # Loading a forceloaded save can tick its entities before the server-ready barrier.
            await command(f"data merge entity {selector} {expected.snbt()}")
            # Native merge is recursive: empty template compounds do not erase startup memories.
            for key, value in expected.items():
                if isinstance(value, nbtlib.Compound):
                    await command(f"data modify entity {selector} {json.dumps(key)} set value {value.snbt()}")
            for key in before.keys() - expected.keys():
                await command(f"data remove entity {selector} {json.dumps(key)}")
            after = await read_camel()
            record["native_after_snbt"] = after.snbt()

            def canonical(value):
                result = nbtlib.parse_nbt(value.snbt())
                result["Attributes"] = nbtlib.List[nbtlib.Compound](
                    sorted(result["Attributes"], key=lambda row: str(row["Name"])))
                # Console SNBT uses shortest float text; compare its exact native IEEE bit width.
                stream = BytesIO()
                nbtlib.File(result).write(stream)
                stream.seek(0)
                return nbtlib.File.parse(stream)

            if canonical(after) != canonical(expected):
                record["differing_root_keys"] = sorted(
                    key for key in after.keys() | expected.keys()
                    if canonical(after).get(key) != canonical(expected).get(key))
                raise RuntimeError("Full native courier NBT differs from the declared template")
            self.initialized = True
            record["restoration_verified"] = True
            record["full_native_nbt_verified"] = True
            record["comparison"] = (
                "Exact full typed binary NBT, excluding save-only id; console SNBT numbers "
                "roundtripped at their declared native bit width; Attributes ordered by registry Name."
            )
            record["restoration_verified_at_ns"] = time.monotonic_ns()
        except BaseException as error:
            record["initialization_error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            receipt.write_text(json.dumps(record, indent=2) + "\n")
