execute as @a at @s unless predicate livequest_quarry:site0 run tag @s remove lqb_quarry_0
execute as @a[tag=!lqb_quarry_0] at @s if predicate livequest_quarry:site0 run function livequest_quarry:enter0
execute as @a at @s unless predicate livequest_quarry:site1 run tag @s remove lqb_quarry_1
execute as @a[tag=!lqb_quarry_1] at @s if predicate livequest_quarry:site1 run function livequest_quarry:enter1
execute as @a at @s unless predicate livequest_quarry:site2 run tag @s remove lqb_quarry_2
execute as @a[tag=!lqb_quarry_2] at @s if predicate livequest_quarry:site2 run function livequest_quarry:enter2
