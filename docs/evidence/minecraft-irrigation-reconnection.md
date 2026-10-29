# Irrigation reconnection qualification

This spatial task uses ordinary water placement, vanilla flow and farmland
hydration. Every marked cell must remain supplied and fully hydrated while the
white walkway stays clear for 100 consecutive native world ticks. The observer
records these conditions; it neither places water nor hydrates farmland.
Residual moisture after removing the water is insufficient.

The final unchanged 2,700-second conditions produced:

| Track | Formal outcome | Native endpoint |
|---|---|---|
| Structured tools | Success, 758.73 seconds | 330 stable ticks; 20 HP; settled return |
| Visual motor | Success at the deadline | 27,111 stable ticks; 20 HP; settled return |

The VM deadline exit is not an invalid measurement or a failure: its saved
endpoint satisfies every public requirement. Both results were independently
audited against retained native snapshots and their captured source hashes.
No unfavorable measurement was replaced.

## Construct and alternatives

The relevant decisions are terrace elevation, reachable placement faces and
containing downhill spill without blocking the walkway. The ST trace includes
placement corrections and water collection/placement at both terraces.
Previously retained native evidence also shows that hydrated fields alone do
not excuse an obstructed walkway. Repairing the authored channels is a useful
strategy, not a secretly required route; other legal water arrangements count.

Relative to abandoned mine cargo (ST 3 / VM 4), this task has fewer route and
retrieval dependencies. Ratings remain **spatial ST 2 / VM 3**. Neither elapsed
hydration time, model latency nor tool-call count establishes difficulty.

The other five dimensions are reviewed but not claimed: supplies do not create
a substantial resource tradeoff; hydration waiting is not reaction pressure;
ordinary terrain observation is not a hidden information-update mechanism;
there is no peer; and familiar vanilla water mechanics do not establish
within-episode learning of an unknown mechanism.

Detailed development provenance is retained under
`output/temp/task_development/minecraft-spi/MC-S04/qualification-review/`.
