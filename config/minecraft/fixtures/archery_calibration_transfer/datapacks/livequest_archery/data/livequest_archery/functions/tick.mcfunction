execute as @a unless score @s lq_prev matches 0.. run scoreboard players set @s lq_prev 0
execute as @a if score @s lq_bow > @s lq_prev run function livequest_archery:shot
