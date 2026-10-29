data modify storage livequest:locks target_1_low set from block 17 73 -5 Items
data modify storage livequest:locks target_1_high set from block 17 73 5 Items
data modify storage livequest:locks target_1_accepted set from block 17 73 8 Items
data modify storage livequest:locks target_2_low set from block 17 73 15 Items
data modify storage livequest:locks target_2_high set from block 17 73 25 Items
data modify storage livequest:locks target_2_accepted set from block 17 73 28 Items
execute store result score #current lq_lock_trace run data get block 49 73 0 OutputSignal
execute unless score #first_raw lq_lock_trace matches 0.. run scoreboard players set #first_raw lq_lock_trace 0
execute if score #current lq_lock_trace > #first_raw lq_lock_trace run scoreboard players operation #first_raw lq_lock_trace = #current lq_lock_trace
execute store result score #current lq_lock_trace run data get block 59 73 0 OutputSignal
execute unless score #first_lower lq_lock_trace matches 0.. run scoreboard players set #first_lower lq_lock_trace 0
execute if score #current lq_lock_trace > #first_lower lq_lock_trace run scoreboard players operation #first_lower lq_lock_trace = #current lq_lock_trace
execute store result score #current lq_lock_trace run data get block 59 73 2 OutputSignal
execute unless score #first_upper lq_lock_trace matches 0.. run scoreboard players set #first_upper lq_lock_trace 0
execute if score #current lq_lock_trace > #first_upper lq_lock_trace run scoreboard players operation #first_upper lq_lock_trace = #current lq_lock_trace
execute store result score #current lq_lock_trace run data get block 54 73 -5 OutputSignal
execute unless score #first_weak lq_lock_trace matches 0.. run scoreboard players set #first_weak lq_lock_trace 0
execute if score #current lq_lock_trace > #first_weak lq_lock_trace run scoreboard players operation #first_weak lq_lock_trace = #current lq_lock_trace
execute if block 67 73 1 redstone_wall_torch[lit=true] run scoreboard players set #first_accept_torch lq_lock_trace 1
execute if block 26 73 5 repeater[powered=true] run scoreboard players set #first_high_end lq_lock_trace 1
execute if block 26 73 8 repeater[powered=true] run scoreboard players set #first_accept_end lq_lock_trace 1
execute store result score #current lq_lock_trace run data get block 50 77 20 OutputSignal
execute unless score #second_raw lq_lock_trace matches 0.. run scoreboard players set #second_raw lq_lock_trace 0
execute if score #current lq_lock_trace > #second_raw lq_lock_trace run scoreboard players operation #second_raw lq_lock_trace = #current lq_lock_trace
execute store result score #current lq_lock_trace run data get block 60 77 20 OutputSignal
execute unless score #second_lower lq_lock_trace matches 0.. run scoreboard players set #second_lower lq_lock_trace 0
execute if score #current lq_lock_trace > #second_lower lq_lock_trace run scoreboard players operation #second_lower lq_lock_trace = #current lq_lock_trace
execute store result score #current lq_lock_trace run data get block 60 77 22 OutputSignal
execute unless score #second_upper lq_lock_trace matches 0.. run scoreboard players set #second_upper lq_lock_trace 0
execute if score #current lq_lock_trace > #second_upper lq_lock_trace run scoreboard players operation #second_upper lq_lock_trace = #current lq_lock_trace
execute store result score #current lq_lock_trace run data get block 55 77 15 OutputSignal
execute unless score #second_weak lq_lock_trace matches 0.. run scoreboard players set #second_weak lq_lock_trace 0
execute if score #current lq_lock_trace > #second_weak lq_lock_trace run scoreboard players operation #second_weak lq_lock_trace = #current lq_lock_trace
execute if block 68 77 21 redstone_wall_torch[lit=true] run scoreboard players set #second_accept_torch lq_lock_trace 1
execute if block 26 73 25 repeater[powered=true] run scoreboard players set #second_high_end lq_lock_trace 1
execute if block 26 73 28 repeater[powered=true] run scoreboard players set #second_accept_end lq_lock_trace 1
