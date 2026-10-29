scoreboard players set #input lqf 0
execute if block 0 72 5 lever[powered=true] run scoreboard players set #input lqf 1
execute unless score #input lqf = #last lqf run scoreboard players operation #pending lqf = #input lqf
execute unless score #input lqf = #last lqf run scoreboard players set #stable lqf 0
scoreboard players set #correct lqf 0
execute if score #input lqf matches 0 if block 0 72 5 lever[powered=false] if block 24 72 5 redstone_lamp[lit=false] if block 24 72 7 iron_door[half=lower,open=false] run scoreboard players set #correct lqf 1
execute if score #input lqf matches 1 if block 0 72 5 lever[powered=true] if block 24 72 5 redstone_lamp[lit=true] if block 24 72 7 iron_door[half=lower,open=true] run scoreboard players set #correct lqf 1
execute if score #correct lqf matches 0 run scoreboard players set #stable lqf 0
execute if score #correct lqf matches 1 run scoreboard players add #stable lqf 1
execute if score #pending lqf matches 0..1 if score #stable lqf matches 1 as @a run function livequest_feedback:start
execute if score #pending lqf matches 0..1 if score #stable lqf matches 100.. as @a run function livequest_feedback:finish
scoreboard players operation #last lqf = #input lqf
