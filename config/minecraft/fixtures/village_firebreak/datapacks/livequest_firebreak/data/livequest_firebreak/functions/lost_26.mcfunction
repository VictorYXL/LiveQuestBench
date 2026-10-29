scoreboard players set #lost26 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;10,73,10]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
