data modify storage livequest:function current set value {station:0,a:0,b:0,lit:0,connections:[]}
execute if block 0 72 0 lever[powered=true] run data modify storage livequest:function current.a set value 1
execute if block 0 72 6 lever[powered=true] run data modify storage livequest:function current.b set value 1
execute if block 0 73 14 redstone_lamp[lit=true] run data modify storage livequest:function current.lit set value 1
execute store success score #changed0 lq_func run data modify storage livequest:function last0 set from storage livequest:function current
execute if score #changed0 lq_func matches 1 run scoreboard players set #stable0 lq_func 0
execute if score #changed0 lq_func matches 0 run scoreboard players add #stable0 lq_func 1
execute if score #stable0 lq_func matches 6 run function livequest_function:record_0
