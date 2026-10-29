scoreboard players set #lost73 lqfire 1
data modify storage livequest:firebreak destroyed append value {cell:[I;22,74,14]}
execute store result storage livequest:firebreak destroyed[-1].tick long 1 run time query gametime
