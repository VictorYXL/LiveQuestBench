data modify storage livequest:trace samples append value {}
data modify storage livequest:trace samples[-1].UUID set from entity @s UUID
data modify storage livequest:trace samples[-1].Pos set from entity @s Pos
data modify storage livequest:trace samples[-1].Motion set from entity @s Motion
data modify storage livequest:trace samples[-1].Health set from entity @s Health
data modify storage livequest:trace samples[-1].Air set from entity @s Air
data modify storage livequest:trace samples[-1].foodLevel set from entity @s foodLevel
data modify storage livequest:trace samples[-1].Inventory set from entity @s Inventory
data modify storage livequest:trace samples[-1].playerGameType set from entity @s playerGameType
execute store result storage livequest:trace samples[-1].tick long 1 run time query gametime
