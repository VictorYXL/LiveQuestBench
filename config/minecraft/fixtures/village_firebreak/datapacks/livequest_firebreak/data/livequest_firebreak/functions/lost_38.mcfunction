scoreboard players set #lost38 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;18,75,11]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
