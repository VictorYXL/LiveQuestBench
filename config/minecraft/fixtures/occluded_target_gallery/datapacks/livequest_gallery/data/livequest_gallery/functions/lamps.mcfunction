data modify storage livequest:gallery lamps set value []
execute if block 29 74 -6 redstone_lamp[lit=true] run data modify storage livequest:gallery lamps append value 1
execute unless block 29 74 -6 redstone_lamp[lit=true] run data modify storage livequest:gallery lamps append value 0
execute if block 29 77 3 redstone_lamp[lit=true] run data modify storage livequest:gallery lamps append value 1
execute unless block 29 77 3 redstone_lamp[lit=true] run data modify storage livequest:gallery lamps append value 0
execute if block 29 80 12 redstone_lamp[lit=true] run data modify storage livequest:gallery lamps append value 1
execute unless block 29 80 12 redstone_lamp[lit=true] run data modify storage livequest:gallery lamps append value 0
