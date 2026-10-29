data modify storage livequest:circuit events append value {}
data modify storage livequest:circuit events[-1].player set from entity @s UUID
execute store result storage livequest:circuit events[-1].tick long 1 run time query gametime
execute store result storage livequest:circuit events[-1].input int 1 run scoreboard players get #input lqb_circuit
scoreboard players set #pending lqb_circuit -1
scoreboard players set #last_clock lqb_circuit -1
