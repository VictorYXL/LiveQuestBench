scoreboard players set #lost15 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;13,75,10]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
