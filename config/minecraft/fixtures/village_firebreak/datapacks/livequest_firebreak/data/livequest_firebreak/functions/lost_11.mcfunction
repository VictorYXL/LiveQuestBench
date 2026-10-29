scoreboard players set #lost11 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;12,75,11]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
