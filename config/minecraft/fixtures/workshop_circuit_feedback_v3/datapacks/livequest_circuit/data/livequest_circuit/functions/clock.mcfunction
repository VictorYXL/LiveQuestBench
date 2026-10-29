execute store result score #clock lqb_circuit run time query gametime
execute unless score #clock lqb_circuit = #last_clock lqb_circuit run function livequest_circuit:sample
scoreboard players operation #last_clock lqb_circuit = #clock lqb_circuit
