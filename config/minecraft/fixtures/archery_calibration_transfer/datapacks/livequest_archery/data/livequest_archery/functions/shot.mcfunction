data modify storage livequest:archery events append value {"kind": "shot"}
data modify storage livequest:archery events[-1].player set from entity @s UUID
execute store result storage livequest:archery events[-1].tick long 1 run time query gametime
execute store result storage livequest:archery events[-1].shots int 1 run scoreboard players get @s lq_bow
scoreboard players operation @s lq_prev = @s lq_bow
