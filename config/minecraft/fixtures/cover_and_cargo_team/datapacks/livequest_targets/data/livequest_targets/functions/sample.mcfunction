data modify storage livequest:targets frames append value {enemies:[]}
execute store result storage livequest:targets frames[-1].tick long 1 run time query gametime
execute as @e[type=minecraft:skeleton] run function livequest_targets:enemy
scoreboard players operation #last lqtarget = #now lqtarget
