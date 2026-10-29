data modify storage livequest:feedback edits append value {}
data modify storage livequest:feedback edits[-1].player set from entity @s UUID
execute store result storage livequest:feedback edits[-1].tick long 1 run time query gametime
scoreboard players set #stable lqf 0
