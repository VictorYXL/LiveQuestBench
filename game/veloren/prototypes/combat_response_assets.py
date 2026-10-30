"""Emit an inert, noncanonical native response proposal; never launch or register it."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import secrets


ABILITY_PATH = Path("common/abilities/custom/green_legoom/doublestrike.ron")
STOCK_SHA256 = "29206ba2f23cab9346b974dede39cb172b91e2ef6bbdc16568fd0c50a31e4a11"
RESPONSE_PARAMETERS = ((0.4, 0.4), (1.2, 1.2))

PUBLIC_PROPOSAL = """NONCANONICAL PROPOSAL, NOT A RUNNABLE OR ACCEPTED TASK.

The proposed episode uses four ordinary Male Green Legoom bodies with the
same visible native rake, name, health and armour. The first strike data, damage,
reach and movement coefficients are unchanged. The native combo commits to its second
strike. Its second buildup and recovery are either both 0.4 seconds or both
1.2 seconds, selected once for the whole episode, not separately per enemy.
Commitment replaces stock input-dependent continuation; chaining skips first recovery.
These are configured native durations, not guaranteed wall-clock hit times.
Interruptions, movement and native attack-speed modifiers remain effective.
Changing stage duration can change movement and hit opportunities. This is
a new native response family, not a claim of unchanged stock combat.
All uses of this ability in the isolated episode share the selected response.

The VM proposal uses ordinary visible attack motion and the effects of legal
movement, rolling and attacks. No damage, failure, block, prescribed probe or
initial encounter order is required. The existing ST interface exposes nearby
body, position and health, but not the raw client's combat phase/timing fields.
Non-contact response discovery through existing ST feedback is unestablished;
this bundle does not change observation permissions or claim ST readiness.
All actually available information, prior knowledge and fresh inspection remain legal.

The proposed nearer encounters are separated; the farther pair shares an
open fighting space. Earlier observations may inform when to disengage or
attack while attending to another enemy. Luring enemies apart, conservative
spacing, reactive inspection and any other legal strategy remain allowed.

The proposed goal is to damage and defeat all four original enemies, never
die and finish with at least one health within 900 seconds, using the starter
sword and three minor potions. There is no secret timing or learning score.
This proposal has not established that history helps over safe generic play,
that the shared encounter is feasible, or that difficulty is moderate.
"""


def render_response(stock: bytes, selection: int) -> bytes:
    """Make only the three declared edits to a byte-pinned native ability."""
    if type(selection) is not int or selection not in range(len(RESPONSE_PARAMETERS)):
        raise ValueError("Select one of the two experimental response parameter pairs")
    if sha256(stock).hexdigest() != STOCK_SHA256:
        raise ValueError("Unreviewed native ability bytes; refuse an unbound rewrite")
    buildup, recovery = RESPONSE_PARAMETERS[selection]
    text = stock.decode("utf-8")
    changes = (
        ("            buildup_duration: 1,", f"            buildup_duration: {buildup},"),
        ("            recover_duration: 1.2,", f"            recover_duration: {recovery},"),
        ("    energy_cost_per_strike: 0,", "    energy_cost_per_strike: 0,\n    auto_progress: true,"),
    )
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError("The reviewed native replacement boundary changed")
        text = text.replace(old, new, 1)
    return text.encode("utf-8")


def build_candidate(asset_root: Path, output: Path, seed: int) -> dict:
    """Write a review bundle, not a fixture or a usable runtime manifest."""
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("The authoring seed must be a u64")
    asset_root, output = asset_root.resolve(), output.resolve()
    if output == asset_root or asset_root in output.parents:
        raise ValueError("Never emit a candidate into the source asset tree")
    stock = (asset_root / ABILITY_PATH).read_bytes()
    selection = random.Random(seed).randrange(len(RESPONSE_PARAMETERS))
    candidate = render_response(stock, selection)
    buildup, recovery = RESPONSE_PARAMETERS[selection]
    receipt = {
        "schema": "noncanonical-native-combat-response-assets/1",
        "status": "inert_asset_experiment_requires_design_and_runtime_admission",
        "canonical": False,
        "qualified": False,
        "runnable_task": False,
        "native_validation": "not_run",
        "source_asset": str(asset_root / ABILITY_PATH),
        "source_sha256": STOCK_SHA256,
        "candidate_sha256": sha256(candidate).hexdigest(),
        "overlay_asset": str(Path("overlay") / ABILITY_PATH),
        "private_authoring_seed": seed,
        "episode_response": {
            "second_buildup_seconds": buildup,
            "second_recovery_seconds": recovery,
            "auto_progress": True,
            "scope": "One shared response for all proposed encounters in this episode",
        },
        "realized_response_count": len(RESPONSE_PARAMETERS),
        "policy_access": "Private authoring receipt; only public-instructions.txt is policy material",
        "activation": "None; no shared assets, fixture allowlist, task, scorer or runtime modified",
        "remaining_gates": [
            "Explicit approval for this new native response family and task distribution",
            "Native asset deserialization and isolated server/client asset-root binding",
            "Public response identifiability and useful changed application, including legal shortcuts",
            "Joint original-health feasibility and a defensible moderate difficulty argument",
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    target = output / "overlay" / ABILITY_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(candidate)
    (output / "private-candidate.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (output / "public-instructions.txt").write_text(PUBLIC_PROPOSAL)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    build_candidate(args.asset_root, args.output, secrets.randbits(64) if args.seed is None else args.seed)
