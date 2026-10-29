package org.livequestbench;

import net.fabricmc.loader.api.entrypoint.PreLaunchEntrypoint;
import net.minecraft.Bootstrap;
import net.minecraft.SharedConstants;
import net.minecraft.block.Blocks;
import net.minecraft.block.RedstoneWireBlock;
import net.minecraft.block.SnowBlock;
import net.minecraft.item.Items;

public final class NativePlacementTest implements PreLaunchEntrypoint {
    @Override
    public void onPreLaunch() {
        main(new String[0]);
        System.exit(0);
    }

    private static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        SharedConstants.createGameVersion();
        Bootstrap.initialize();
        var air = Blocks.AIR.getDefaultState();
        var wire = Blocks.REDSTONE_WIRE.getDefaultState();
        require(NativeBridge.matchesPlacedBlock(Items.REDSTONE, air, wire, true),
                "Observed redstone item -> redstone_wire block placement must be confirmed");
        require(NativeBridge.matchesPlacedBlock(Items.TORCH, air, Blocks.WALL_TORCH.getDefaultState(), true),
                "Native wall variant must retain its placement item identity");
        require(NativeBridge.matchesPlacedBlock(Items.COBBLESTONE, air, Blocks.COBBLESTONE.getDefaultState(), true),
                "Ordinary same-name block placement must remain supported");
        require(!NativeBridge.matchesPlacedBlock(Items.REDSTONE, air, air, true),
                "Missing placement must not succeed");
        require(!NativeBridge.matchesPlacedBlock(Items.REDSTONE, wire, wire, true),
                "Unchanged target must not succeed");
        require(!NativeBridge.matchesPlacedBlock(Items.REDSTONE, air, Blocks.COBBLESTONE.getDefaultState(), true),
                "An unrelated changed block must not succeed");
        require(!NativeBridge.matchesPlacedBlock(Items.REDSTONE, wire, wire.with(RedstoneWireBlock.POWER, 15), false),
                "Power changes on occupied wire are not placements");
        var snow = Blocks.SNOW.getDefaultState();
        require(NativeBridge.matchesPlacedBlock(Items.SNOW, snow, snow.with(SnowBlock.LAYERS, 2), true),
                "Native-replaceable same-block layering must remain supported");
        require(!NativeBridge.matchesPlacedBlock(Items.DIAMOND, air, Blocks.DIAMOND_BLOCK.getDefaultState(), true),
                "A non-block item must not confirm a block");
        System.out.println("9 native placement confirmation cases passed");
    }
}
