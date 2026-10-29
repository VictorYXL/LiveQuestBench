scoreboard players set #lost9 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;11,75,14]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
