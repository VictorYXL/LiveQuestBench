scoreboard players set #burn0 lqb_furn 0
execute store result score #burn0 lqb_furn run data get block -9 72 2 BurnTime
scoreboard players set #input0 lqb_furn 0
execute store result score #input0 lqb_furn run data get block -9 72 2 Items[{Slot:0b}].Count
scoreboard players set #output0 lqb_furn 0
execute store result score #output0 lqb_furn run data get block -9 72 2 Items[{Slot:2b}].Count
execute if score #burn0 lqb_furn matches 1.. run scoreboard players add #burning0 lqb_furn 1
execute if score #burn0 lqb_furn matches 1.. if score #input0 lqb_furn matches 0 run scoreboard players add #empty0 lqb_furn 1
execute if score #output0 lqb_furn > #lastout0 lqb_furn run function livequest_furnaces:output0
execute if score #burn0 lqb_furn > #lastburn0 lqb_furn run function livequest_furnaces:fuel0
execute if data block -9 72 2 Items[{Slot:1b}] run data modify storage livequest:dispatch fuel0 set from block -9 72 2 Items[{Slot:1b}].id
scoreboard players operation #lastout0 lqb_furn = #output0 lqb_furn
scoreboard players operation #lastburn0 lqb_furn = #burn0 lqb_furn
execute store result storage livequest:dispatch metrics[0].burning_ticks long 1 run scoreboard players get #burning0 lqb_furn
execute store result storage livequest:dispatch metrics[0].empty_input_burn_ticks long 1 run scoreboard players get #empty0 lqb_furn
scoreboard players set #burn1 lqb_furn 0
execute store result score #burn1 lqb_furn run data get block 9 72 2 BurnTime
scoreboard players set #input1 lqb_furn 0
execute store result score #input1 lqb_furn run data get block 9 72 2 Items[{Slot:0b}].Count
scoreboard players set #output1 lqb_furn 0
execute store result score #output1 lqb_furn run data get block 9 72 2 Items[{Slot:2b}].Count
execute if score #burn1 lqb_furn matches 1.. run scoreboard players add #burning1 lqb_furn 1
execute if score #burn1 lqb_furn matches 1.. if score #input1 lqb_furn matches 0 run scoreboard players add #empty1 lqb_furn 1
execute if score #output1 lqb_furn > #lastout1 lqb_furn run function livequest_furnaces:output1
execute if score #burn1 lqb_furn > #lastburn1 lqb_furn run function livequest_furnaces:fuel1
execute if data block 9 72 2 Items[{Slot:1b}] run data modify storage livequest:dispatch fuel1 set from block 9 72 2 Items[{Slot:1b}].id
scoreboard players operation #lastout1 lqb_furn = #output1 lqb_furn
scoreboard players operation #lastburn1 lqb_furn = #burn1 lqb_furn
execute store result storage livequest:dispatch metrics[1].burning_ticks long 1 run scoreboard players get #burning1 lqb_furn
execute store result storage livequest:dispatch metrics[1].empty_input_burn_ticks long 1 run scoreboard players get #empty1 lqb_furn
