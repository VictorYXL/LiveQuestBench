execute store result score #clock lqf run time query gametime
execute unless score #clock lqf = #last_clock lqf run function livequest_feedback:sample
scoreboard players operation #last_clock lqf = #clock lqf
