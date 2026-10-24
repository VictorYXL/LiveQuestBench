data modify storage livequest:actions events append value {kind:"damage"}
data modify storage livequest:actions events[-1].player set from entity @s UUID
execute store result storage livequest:actions events[-1].tick long 1 run time query gametime
advancement revoke @s only livequest_actions:damage
