data modify storage livequest:air samples append value {active_effects:[]}
data modify storage livequest:air samples[-1].UUID set from entity @s UUID
data modify storage livequest:air samples[-1].Pos set from entity @s Pos
data modify storage livequest:air samples[-1].Health set from entity @s Health
data modify storage livequest:air samples[-1].Air set from entity @s Air
data modify storage livequest:air samples[-1].active_effects set from entity @s active_effects
execute store result storage livequest:air samples[-1].tick long 1 run time query gametime
