import asyncio
import pytest

from game.minecraft.runtime.bridge import BridgeError
from game.minecraft.structured_tools.interface import execute_tool


def test_vitals_reads_own_native_rpc_without_submitting_actions():
    class Bridge:
        calls = []

        async def request(self, method, arguments):
            self.calls.append((method, arguments))
            return {"success": True, "payload": {
                "air_ticks": 120, "max_air_ticks": 300, "submerged_in_water": True,
                "effects": [{"id": "minecraft:water_breathing", "amplifier": 0, "duration_ticks": 40}],
            }}

    bridge = Bridge()
    result = asyncio.run(execute_tool(bridge, "InspectVitalsTool", {}))
    assert result["payload"]["air_ticks"] == 120
    assert result["payload"]["effects"][0]["duration_ticks"] == 40
    assert bridge.calls == [("vitals", {})]
    with pytest.raises(ValueError):
        asyncio.run(execute_tool(bridge, "InspectVitalsTool", {"player": "Other"}))
    assert len(bridge.calls) == 1


def test_vitals_rejects_malformed_bridge_readback():
    class Bridge:
        async def request(self, method, arguments):
            return {"payload": {"air_ticks": 300}}

    with pytest.raises(BridgeError, match="Malformed ST action result"):
        asyncio.run(execute_tool(Bridge(), "InspectVitalsTool", {}))
