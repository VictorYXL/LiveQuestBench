data modify storage livequest:gallery hits append value {target:1}
data modify storage livequest:gallery hits[-1].player set from entity @s UUID
execute store result storage livequest:gallery hits[-1].tick long 1 run time query gametime
