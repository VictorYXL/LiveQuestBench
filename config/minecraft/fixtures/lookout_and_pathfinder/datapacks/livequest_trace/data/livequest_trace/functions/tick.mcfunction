scoreboard players add #clock lqtrace 1
execute if score #clock lqtrace matches 20.. as @a run function livequest_trace:sample
execute if score #clock lqtrace matches 20.. run scoreboard players set #clock lqtrace 0
