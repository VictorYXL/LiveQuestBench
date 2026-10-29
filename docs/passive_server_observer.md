# Approved passive successful-break prototype

`server_observer/` is an isolated Fabric 1.20.4 server-side mixin, built with the
same pinned loader/Yarn/Loom versions already used by the native client.
It observes `tryBreakBlock` entry/return, records only a successful return with
an actual change from the original non-air block, and appends player UUID,
dimension, position, old type and native tick. It never cancels a break,
changes a block, awards an item or sends evidence to the agent.

`runtime/observed_server.py` is explicitly opt-in. The default vanilla runtime
is untouched. Build using the existing Gradle 8.6 executable with a project-local
cache and Java scratch directory, then run `prepareServer`. Its generated
`launch.json` is local build output, not checked-in or portable evidence.
Set `LIVEQUEST_BREAK_SERVER_LAUNCH` only for an approved centrally leased
prototype. Do not copy this runtime into unrelated task worktrees.

At the original blueprint-prototype closure, the Java build succeeded. Four focused offline tests verified rotated blueprint
clearance/materials and attribution/time/removal-budget handling. The full native
blueprint witness was operator-cancelled when the user requested hidden-mechanism
learning instead; native break-hook correctness was then unverified.
Compilation alone did not establish native success or learning.

Preserved artifacts:
- `output/temp/task_development/MC-L05-approved-contrast-author`
- `output/temp/task_development/MC-L05-approved-contrast-fixture`
- `output/temp/task_development/MC-L05-approved-contrast-native-v1`
- `output/temp/task_development/MC-L05-observer-build.log`

The cold blueprint script and scorer are retained as an explicitly superseded
construction contrast, not an adopted learning task. Any L05-M functional-rule
prototype subsequently received explicit objective approval. The retained
`MC-L05-native-function-proof-v4` records an actual owned successful removal
with the unchanged compiled observer. Full task bindings now opt in per session
via a server factory, without globally replacing the vanilla server class.
See `native_hidden_function.md` for current full-task verification and limits.
