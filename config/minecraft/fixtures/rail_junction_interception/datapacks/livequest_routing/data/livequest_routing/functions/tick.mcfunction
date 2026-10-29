scoreboard players add #sample lq_route 1
execute if score #sample lq_route matches 10.. run function livequest_routing:sample
execute if score #sample lq_route matches 10.. run scoreboard players set #sample lq_route 0
