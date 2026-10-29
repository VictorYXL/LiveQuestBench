scoreboard players set #lost56 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;21,75,14]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
