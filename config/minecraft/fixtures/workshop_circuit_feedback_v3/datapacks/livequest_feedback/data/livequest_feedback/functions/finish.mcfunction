function livequest_feedback:count_mined
execute if score #mined lqf = #start_mined lqf run function livequest_feedback:record
execute unless score #mined lqf = #start_mined lqf run scoreboard players set #stable lqf 0
