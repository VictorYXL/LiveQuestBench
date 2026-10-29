scoreboard players set #phase lqswitch 1
data modify storage livequest:switch events append value {application:1}
data modify storage livequest:switch events[-1].player set from entity @s UUID
execute store result storage livequest:switch events[-1].tick long 1 run time query gametime
