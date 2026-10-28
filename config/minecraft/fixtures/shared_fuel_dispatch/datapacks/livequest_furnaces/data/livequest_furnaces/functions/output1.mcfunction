data modify storage livequest:dispatch events append value {kind:"completion",machine:1}
execute store result storage livequest:dispatch events[-1].tick long 1 run time query gametime
data modify storage livequest:dispatch events[-1].output set from block 9 72 2 Items[{Slot:2b}]
