scoreboard players set #lost25 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;10,72,10]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
