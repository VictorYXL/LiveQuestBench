scoreboard players add #sequence lq_event 1
data modify storage livequest:expedition purchases append value {item:"minecraft:iron_axe",merchant:"624fda3c-ac53-4693-9bdc-28b2e310ed88"}
data modify storage livequest:expedition purchases[-1].player set from entity @s UUID
execute store result storage livequest:expedition purchases[-1].tick long 1 run time query gametime
execute store result storage livequest:expedition purchases[-1].sequence int 1 run scoreboard players get #sequence lq_event
