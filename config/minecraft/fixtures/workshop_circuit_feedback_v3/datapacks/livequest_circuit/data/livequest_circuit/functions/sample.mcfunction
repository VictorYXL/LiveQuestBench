scoreboard players set #input lqb_circuit 0
execute if block 0 72 5 lever[powered=true] run scoreboard players set #input lqb_circuit 1
execute unless score #input lqb_circuit = #last lqb_circuit run scoreboard players operation #pending lqb_circuit = #input lqb_circuit
execute unless score #input lqb_circuit = #last lqb_circuit run scoreboard players set #stable lqb_circuit 0
scoreboard players set #correct lqb_circuit 0
execute if score #input lqb_circuit matches 0 if block 0 72 5 lever[powered=false] if block 24 72 5 redstone_lamp[lit=false] if block 24 72 7 iron_door[half=lower,open=false] run scoreboard players set #correct lqb_circuit 1
execute if score #input lqb_circuit matches 1 if block 0 72 5 lever[powered=true] if block 24 72 5 redstone_lamp[lit=true] if block 24 72 7 iron_door[half=lower,open=true] run scoreboard players set #correct lqb_circuit 1
execute if score #correct lqb_circuit matches 1 run scoreboard players add #stable lqb_circuit 1
execute if score #correct lqb_circuit matches 0 run scoreboard players set #stable lqb_circuit 0
execute if score #pending lqb_circuit matches 0..1 if score #stable lqb_circuit matches 10.. as @a run function livequest_circuit:record
scoreboard players operation #last lqb_circuit = #input lqb_circuit
