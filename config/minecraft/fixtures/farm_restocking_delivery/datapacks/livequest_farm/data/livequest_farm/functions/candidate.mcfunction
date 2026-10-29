execute store result score @s lqb_farm_age run data get entity @s Age
execute if score @s lqb_farm_age matches -24000..-23998 run data modify storage livequest:farm events[-1].children append from entity @s UUID
execute if score @s lqb_farm_age matches -24000..-23998 run tag @s add lqb_farm_child
