function livequest_feedback:count_mined
scoreboard players operation #start_mined lqf = #mined lqf
execute store result score #start_tick lqf run time query gametime
