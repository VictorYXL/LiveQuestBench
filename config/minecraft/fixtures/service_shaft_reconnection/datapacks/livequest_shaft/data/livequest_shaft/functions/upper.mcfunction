data modify storage livequest:shaft visits append value {}
data modify storage livequest:shaft visits[-1].player set from entity @s UUID
execute store result storage livequest:shaft visits[-1].tick long 1 run time query gametime
tag @s add lqb_shaft_upper
