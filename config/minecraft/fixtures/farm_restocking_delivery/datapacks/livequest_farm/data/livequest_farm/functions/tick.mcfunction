execute if data storage livequest:farm schema run data modify storage livequest:farm alive set value []
execute if data storage livequest:farm schema as @e[type=sheep,tag=lqb_farm_child,nbt=!{Health:0.0f}] run data modify storage livequest:farm alive append from entity @s UUID
