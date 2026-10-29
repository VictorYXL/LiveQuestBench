data modify storage livequest:quarry visits append value {site:0}
data modify storage livequest:quarry visits[-1].player set from entity @s UUID
execute store result storage livequest:quarry visits[-1].tick long 1 run time query gametime
tag @s add lqb_quarry_0
