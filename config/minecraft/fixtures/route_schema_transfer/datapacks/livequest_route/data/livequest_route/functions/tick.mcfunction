execute store result score #samples lq_route run data get storage livequest:route samples
execute if score #samples lq_route matches ..89999 as @a at @s run function livequest_route:sample
execute if score #samples lq_route matches 90000.. run data modify storage livequest:route overflow set value 1b
