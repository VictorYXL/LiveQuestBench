scoreboard players set #lost72 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;22,73,14]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
