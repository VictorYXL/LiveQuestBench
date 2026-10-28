data modify storage livequest:route samples append value {}
data modify storage livequest:route samples[-1].player set from entity @s UUID
data modify storage livequest:route samples[-1].position set from entity @s Pos
execute store result storage livequest:route samples[-1].tick long 1 run time query gametime
