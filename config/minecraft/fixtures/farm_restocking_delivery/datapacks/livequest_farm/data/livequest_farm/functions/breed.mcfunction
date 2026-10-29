data modify storage livequest:farm events append value {children:[]}
data modify storage livequest:farm events[-1].player set from entity @s UUID
execute store result storage livequest:farm events[-1].tick long 1 run time query gametime
tag @e[type=sheep] add lqb_farm_prebirth
schedule function livequest_farm:collect_child 1t replace
advancement revoke @s only livequest_farm:breed
