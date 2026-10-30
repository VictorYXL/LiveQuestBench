data modify storage livequest:function events append from storage livequest:function current
execute store result storage livequest:function events[-1].tick long 1 run time query gametime
