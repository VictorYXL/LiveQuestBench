data modify storage livequest:routing samples append value {east_warning:0,west_warning:0}
execute store result storage livequest:routing samples[-1].tick long 1 run time query gametime
data modify storage livequest:routing samples[-1].east_pos set from entity @e[type=chest_minecart,tag=original_cart_east,limit=1] Pos
execute if block -5 72 -8 piston_head run data modify storage livequest:routing samples[-1].east_warning set value 1
data modify storage livequest:routing samples[-1].west_pos set from entity @e[type=chest_minecart,tag=original_cart_west,limit=1] Pos
execute if block 7 72 -8 piston_head run data modify storage livequest:routing samples[-1].west_warning set value 1
