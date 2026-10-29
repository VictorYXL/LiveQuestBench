execute store result storage livequest:farm events[-1].captured_tick long 1 run time query gametime
execute at @e[type=sheep,tag=lqb_parent_a,limit=1] as @e[type=sheep,tag=!lqb_farm_prebirth,distance=..4] run function livequest_farm:candidate
