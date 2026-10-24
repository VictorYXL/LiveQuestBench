scoreboard players add #sequence lq_event 1
scoreboard players add @s lq_stone 0
scoreboard players add @s lq_iron 0
data modify storage livequest:expedition kills append value {role:"spider",stone:0,iron:0,hand:""}
data modify storage livequest:expedition kills[-1].player set from entity @s UUID
data modify storage livequest:expedition kills[-1].hand set from entity @s SelectedItem.id
execute store result storage livequest:expedition kills[-1].tick long 1 run time query gametime
execute store result storage livequest:expedition kills[-1].stone int 1 run scoreboard players get @s lq_stone
execute store result storage livequest:expedition kills[-1].iron int 1 run scoreboard players get @s lq_iron
execute store result storage livequest:expedition kills[-1].sequence int 1 run scoreboard players get #sequence lq_event
