scoreboard players add #sample lq_func 1
execute if score #sample lq_func matches 10.. run function livequest_function:sample
execute if score #sample lq_func matches 10.. run scoreboard players set #sample lq_func 0
