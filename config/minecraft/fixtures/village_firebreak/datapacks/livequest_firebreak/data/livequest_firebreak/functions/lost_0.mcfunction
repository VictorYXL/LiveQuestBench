scoreboard players set #lost0 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;10,75,10]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
