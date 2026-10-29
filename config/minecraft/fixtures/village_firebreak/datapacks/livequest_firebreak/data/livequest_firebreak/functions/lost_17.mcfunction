scoreboard players set #lost17 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;13,75,12]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
