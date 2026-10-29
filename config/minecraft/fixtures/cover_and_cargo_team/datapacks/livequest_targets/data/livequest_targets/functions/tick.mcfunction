execute store result score #now lqtarget run time query gametime
scoreboard players operation #elapsed lqtarget = #now lqtarget
scoreboard players operation #elapsed lqtarget -= #last lqtarget
execute if score #elapsed lqtarget matches 20.. run function livequest_targets:sample
