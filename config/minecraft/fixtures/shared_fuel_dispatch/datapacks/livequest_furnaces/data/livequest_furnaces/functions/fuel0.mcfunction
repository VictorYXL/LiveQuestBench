data modify storage livequest:dispatch events append value {kind:"fuel",machine:0}
execute store result storage livequest:dispatch events[-1].tick long 1 run time query gametime
data modify storage livequest:dispatch events[-1].item set from storage livequest:dispatch fuel0
