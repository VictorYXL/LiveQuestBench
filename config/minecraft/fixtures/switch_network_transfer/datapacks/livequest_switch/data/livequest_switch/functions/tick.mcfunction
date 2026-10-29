execute if entity @a[x=-1,y=170,z=30,dx=5,dy=8,dz=90] run scoreboard players set #active lqswitch 1
execute if score #c0i0 lqswitch matches 0 if block 3 173 2 minecraft:lever[powered=true] run function livequest_switch:c0i0_1
execute if score #c0i0 lqswitch matches 1 if block 3 173 2 minecraft:lever[powered=false] run function livequest_switch:c0i0_0
execute if score #c0i1 lqswitch matches 0 if block 3 173 6 minecraft:lever[powered=true] run function livequest_switch:c0i1_1
execute if score #c0i1 lqswitch matches 1 if block 3 173 6 minecraft:lever[powered=false] run function livequest_switch:c0i1_0
execute if score #c0i2 lqswitch matches 0 if block 3 173 10 minecraft:lever[powered=true] run function livequest_switch:c0i2_1
execute if score #c0i2 lqswitch matches 1 if block 3 173 10 minecraft:lever[powered=false] run function livequest_switch:c0i2_0
execute if score #c1i0 lqswitch matches 0 if block 3 173 46 minecraft:lever[powered=true] run function livequest_switch:c1i0_1
execute if score #c1i0 lqswitch matches 1 if block 3 173 46 minecraft:lever[powered=false] run function livequest_switch:c1i0_0
execute if score #c1i1 lqswitch matches 0 if block 3 173 50 minecraft:lever[powered=true] run function livequest_switch:c1i1_1
execute if score #c1i1 lqswitch matches 1 if block 3 173 50 minecraft:lever[powered=false] run function livequest_switch:c1i1_0
execute if score #c1i2 lqswitch matches 0 if block 3 173 42 minecraft:lever[powered=true] run function livequest_switch:c1i2_1
execute if score #c1i2 lqswitch matches 1 if block 3 173 42 minecraft:lever[powered=false] run function livequest_switch:c1i2_0
execute if score #c2i0 lqswitch matches 0 if block 3 173 90 minecraft:lever[powered=true] run function livequest_switch:c2i0_1
execute if score #c2i0 lqswitch matches 1 if block 3 173 90 minecraft:lever[powered=false] run function livequest_switch:c2i0_0
execute if score #c2i1 lqswitch matches 0 if block 3 173 82 minecraft:lever[powered=true] run function livequest_switch:c2i1_1
execute if score #c2i1 lqswitch matches 1 if block 3 173 82 minecraft:lever[powered=false] run function livequest_switch:c2i1_0
execute if score #c2i2 lqswitch matches 0 if block 3 173 86 minecraft:lever[powered=true] run function livequest_switch:c2i2_1
execute if score #c2i2 lqswitch matches 1 if block 3 173 86 minecraft:lever[powered=false] run function livequest_switch:c2i2_0
data modify storage livequest:switch ready_1 set value 0b
execute if block 4 173 62 minecraft:redstone_lamp[lit=false] if block 4 173 58 minecraft:redstone_lamp[lit=true] if block 4 173 54 minecraft:redstone_lamp[lit=false] run data modify storage livequest:switch ready_1 set value 1b
execute if score #phase lqswitch matches 0 if score #practice lqswitch matches 1.. as @a[x=-1,y=170,z=40,dx=5,dy=8,dz=25] if block 4 173 62 minecraft:redstone_lamp[lit=false] if block 4 173 58 minecraft:redstone_lamp[lit=true] if block 4 173 54 minecraft:redstone_lamp[lit=false] run function livequest_switch:goal_1
data modify storage livequest:switch ready_2 set value 0b
execute if block 4 173 98 minecraft:redstone_lamp[lit=true] if block 4 173 94 minecraft:redstone_lamp[lit=false] if block 4 173 102 minecraft:redstone_lamp[lit=false] run data modify storage livequest:switch ready_2 set value 1b
execute if score #phase lqswitch matches 1 if score #practice lqswitch matches 1.. as @a[x=-1,y=170,z=80,dx=5,dy=8,dz=25] if block 4 173 98 minecraft:redstone_lamp[lit=true] if block 4 173 94 minecraft:redstone_lamp[lit=false] if block 4 173 102 minecraft:redstone_lamp[lit=false] run function livequest_switch:goal_2
execute store result storage livequest:switch application_toggles int 1 run scoreboard players get #toggles lqswitch
execute store result storage livequest:switch practice_toggles int 1 run scoreboard players get #practice lqswitch
execute store result storage livequest:switch phase int 1 run scoreboard players get #phase lqswitch
execute if block 4 173 14 minecraft:redstone_lamp[lit=true] run data modify storage livequest:switch practice_feedback set value 1b
execute if block 4 173 18 minecraft:redstone_lamp[lit=true] run data modify storage livequest:switch practice_feedback set value 1b
execute if block 4 173 22 minecraft:redstone_lamp[lit=true] run data modify storage livequest:switch practice_feedback set value 1b
