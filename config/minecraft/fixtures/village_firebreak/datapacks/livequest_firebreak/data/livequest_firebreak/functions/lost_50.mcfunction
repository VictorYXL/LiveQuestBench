scoreboard players set #lost50 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;20,75,13]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
