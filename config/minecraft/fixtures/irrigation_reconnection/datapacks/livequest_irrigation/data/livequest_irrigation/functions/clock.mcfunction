execute store result score #clock lqb_water run time query gametime
execute unless score #clock lqb_water = #last_clock lqb_water run function livequest_irrigation:sample
scoreboard players operation #last_clock lqb_water = #clock lqb_water
