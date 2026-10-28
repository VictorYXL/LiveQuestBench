data modify storage livequest:shield events append value {kind:"skeleton_arrow_block"}
data modify storage livequest:shield events[-1].player set from entity @s UUID
execute store result storage livequest:shield events[-1].tick long 1 run time query gametime
advancement revoke @s only livequest_shield:block
