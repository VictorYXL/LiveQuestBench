data modify storage livequest:targets current set value {target_is_player:0b}
data modify storage livequest:targets current.enemy set from entity @s UUID
execute on target run data modify storage livequest:targets current.target set from entity @s UUID
execute on target if entity @s[type=minecraft:player] run data modify storage livequest:targets current.target_is_player set value 1b
data modify storage livequest:targets frames[-1].enemies append from storage livequest:targets current
