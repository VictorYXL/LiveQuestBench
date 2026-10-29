data modify storage livequest:feedback events append value {}
data modify storage livequest:feedback events[-1].player set from entity @s UUID
execute store result storage livequest:feedback events[-1].tick long 1 run time query gametime
execute store result storage livequest:feedback events[-1].start_tick long 1 run scoreboard players get #start_tick lqf
execute store result storage livequest:feedback events[-1].input int 1 run scoreboard players get #input lqf
execute store result storage livequest:feedback events[-1].mined int 1 run scoreboard players get #mined lqf
execute store result storage livequest:feedback events[-1].edits int 1 run data get storage livequest:feedback edits
scoreboard players set #pending lqf -1
