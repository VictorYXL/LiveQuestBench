package org.livequestbench;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.minecraft.block.entity.AbstractFurnaceBlockEntity;
import net.minecraft.client.gui.screen.ingame.InventoryScreen;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.recipe.*;
import net.minecraft.registry.Registries;
import net.minecraft.screen.*;
import net.minecraft.screen.slot.Slot;
import net.minecraft.screen.slot.SlotActionType;
import net.minecraft.util.Hand;
import net.minecraft.util.hit.BlockHitResult;
import java.util.*;

final class NativeInventory {
    private static List<RecipeEntry<CraftingRecipe>> craftingRecipes(JsonObject params) {
        var mc = NativeBridge.client();
        String output = NativeBridge.text(params, "output_item", "").replace("minecraft:", "");
        int size = NativeBridge.text(params, "station", "inventory").equals("crafting_table") ? 3 : 2;
        return mc.world.getRecipeManager().listAllOfType(RecipeType.CRAFTING).stream()
                .filter(entry -> NativeBridge.itemName(entry.value().getResult(mc.world.getRegistryManager())).equals(output)
                        && entry.value().fits(size, size))
                .sorted(Comparator.comparing(entry -> entry.id().toString())).toList();
    }

    private static boolean craftable(CraftingRecipe recipe) {
        RecipeMatcher matcher = new RecipeMatcher();
        NativeBridge.client().player.getInventory().populateRecipeFinder(matcher);
        return matcher.match(recipe, null);
    }

    static JsonObject recipes(JsonObject params) {
        JsonArray result = new JsonArray();
        var matches = craftingRecipes(params);
        for (int i = 0; i < matches.size(); i++) {
            var recipe = matches.get(i);
            JsonArray ingredients = new JsonArray();
            for (Ingredient ingredient : recipe.value().getIngredients()) {
                if (ingredient.isEmpty()) continue;
                JsonArray alternatives = new JsonArray();
                for (ItemStack stack : ingredient.getMatchingStacks()) alternatives.add(NativeBridge.itemName(stack));
                ingredients.add(alternatives);
            }
            result.add(NativeBridge.object("recipe_index", i, "id", recipe.id().toString(),
                    "craftable", craftable(recipe.value()), "ingredients", ingredients,
                    "output_count", recipe.value().getResult(NativeBridge.client().world.getRegistryManager()).getCount()));
        }
        return NativeBridge.object("recipes", result);
    }

    static int count(String item) {
        int count = 0;
        for (int i = 0; i < 36; i++) {
            ItemStack stack = NativeBridge.client().player.getInventory().getStack(i);
            if (NativeBridge.itemName(stack).equals(item)) count += stack.getCount();
        }
        return count;
    }

    static void click(int slot, int button, SlotActionType action) {
        var mc = NativeBridge.client();
        mc.interactionManager.clickSlot(mc.player.currentScreenHandler.syncId, slot, button, action, mc.player);
    }

    private static boolean openStation(String name) {
        var mc = NativeBridge.client();
        if (mc.player.currentScreenHandler != mc.player.playerScreenHandler) mc.player.closeHandledScreen();
        BlockHitResult hit = NativeBridge.aimedBlock();
        if (hit == null || !Registries.BLOCK.getId(mc.world.getBlockState(hit.getBlockPos()).getBlock()).getPath().equals(name))
            return false;
        if (!mc.interactionManager.interactBlock(mc.player, Hand.MAIN_HAND, hit).isAccepted()) return false;
        mc.player.swingHand(Hand.MAIN_HAND);
        return true;
    }

    static NativeBridge.Job inspectContainer() {
        var current = NativeBridge.client().player.currentScreenHandler;
        if (!(current instanceof GenericContainerScreenHandler) && !openStation("chest"))
            return () -> NativeBridge.fail("Aim at a reachable chest or open a native chest-cart screen first");
        long started = System.nanoTime();
        return () -> {
            var handler = NativeBridge.client().player.currentScreenHandler;
            if (!(handler instanceof GenericContainerScreenHandler container)) {
                return System.nanoTime() - started > 3_000_000_000L
                        ? NativeBridge.fail("Native chest screen did not open") : null;
            }
            JsonArray items = new JsonArray();
            for (int slot = 0; slot < container.getRows() * 9; slot++) {
                var stack = handler.getSlot(slot).getStack();
                if (!stack.isEmpty()) items.add(NativeBridge.item(stack, slot));
            }
            return NativeBridge.ok("slots", container.getRows() * 9, "items", items);
        };
    }

    static NativeBridge.Job takeContainerItem(JsonObject params) {
        var handler = NativeBridge.client().player.currentScreenHandler;
        if (!(handler instanceof GenericContainerScreenHandler container))
            return () -> NativeBridge.fail("Inspect a chest before taking an item");
        int slot = params.get("slot").getAsInt();
        if (slot < 0 || slot >= container.getRows() * 9 || handler.getSlot(slot).getStack().isEmpty())
            return () -> NativeBridge.fail("Container slot is empty or out of range");
        if (!handler.getCursorStack().isEmpty()) return () -> NativeBridge.fail("Clear the inventory cursor first");
        int before = handler.getSlot(slot).getStack().getCount();
        click(slot, 0, SlotActionType.QUICK_MOVE);
        long started = System.nanoTime();
        return () -> {
            if (NativeBridge.client().player.currentScreenHandler != handler)
                return NativeBridge.fail("Container screen closed during transfer");
            if (System.nanoTime() - started < 250_000_000L) return null;
            int moved = before - handler.getSlot(slot).getStack().getCount();
            if (moved > 0) return NativeBridge.ok("moved_count", moved, "slot", slot);
            return System.nanoTime() - started > 3_000_000_000L
                    ? NativeBridge.fail("No native transfer confirmed; inventory may be full") : null;
        };
    }

    private static JsonObject furnaceState(FurnaceScreenHandler furnace) {
        JsonArray slots = new JsonArray();
        for (Slot slot : furnace.slots) {
            slots.add(NativeBridge.object("slot", slot.id, "item", NativeBridge.item(slot.getStack(), slot.id)));
        }
        return NativeBridge.ok("slots", slots, "cursor", NativeBridge.item(furnace.getCursorStack(), -1),
                "burning", furnace.isBurning(), "cook_progress", furnace.getCookProgress(),
                "fuel_progress", furnace.getFuelProgress());
    }

    static NativeBridge.Job inspectFurnace() {
        var mc = NativeBridge.client();
        if (!(mc.player.currentScreenHandler instanceof FurnaceScreenHandler) && !openStation("furnace"))
            return () -> NativeBridge.fail("Aim at a reachable furnace first");
        long started = System.nanoTime();
        return () -> {
            if (mc.player.currentScreenHandler instanceof FurnaceScreenHandler furnace)
                return furnaceState(furnace);
            return System.nanoTime() - started > 3_000_000_000L
                    ? NativeBridge.fail("Native furnace screen did not open") : null;
        };
    }

    static NativeBridge.Job clickFurnace(JsonObject params) {
        var mc = NativeBridge.client();
        if (!(mc.player.currentScreenHandler instanceof FurnaceScreenHandler furnace))
            return () -> NativeBridge.fail("Inspect a furnace before clicking its slots");
        int slot = params.get("slot").getAsInt();
        String button = NativeBridge.text(params, "button", "");
        String operation = NativeBridge.text(params, "operation", "");
        if (slot < 0 || slot >= furnace.slots.size()
                || !(button.equals("left") || button.equals("right"))
                || !(operation.equals("pickup") || operation.equals("quick_move")))
            return () -> NativeBridge.fail("Invalid native furnace click");
        click(slot, button.equals("left") ? 0 : 1,
                operation.equals("pickup") ? SlotActionType.PICKUP : SlotActionType.QUICK_MOVE);
        long started = System.nanoTime();
        return () -> {
            if (mc.player.currentScreenHandler != furnace)
                return NativeBridge.fail("Furnace screen closed after click; partial effects persist");
            if (System.nanoTime() - started < 250_000_000L) return null;
            JsonObject result = furnaceState(furnace);
            result.getAsJsonObject("payload").addProperty("click_submitted", true);
            return result;
        };
    }

    static NativeBridge.Job craft(JsonObject params) {
        var mc = NativeBridge.client();
        var matches = craftingRecipes(params);
        int recipeIndex = params.has("recipe_index") ? params.get("recipe_index").getAsInt() : -1;
        if (!params.has("recipe_index")) {
            for (int i = 0; i < matches.size(); i++) if (craftable(matches.get(i).value())) { recipeIndex = i; break; }
        }
        if (recipeIndex < 0 || recipeIndex >= matches.size()) return () -> NativeBridge.fail("Craft recipe not found");
        var recipe = matches.get(recipeIndex);
        if (!craftable(recipe.value())) return () -> NativeBridge.fail("Insufficient ingredients for recipe");
        if (!mc.player.currentScreenHandler.getCursorStack().isEmpty()) return () -> NativeBridge.fail("Clear the inventory cursor before crafting");
        boolean table = NativeBridge.text(params, "station", "inventory").equals("crafting_table");
        if (table) {
            if (!openStation("crafting_table")) return () -> NativeBridge.fail("Aim at a reachable crafting table first");
        } else {
            if (mc.player.currentScreenHandler != mc.player.playerScreenHandler) mc.player.closeHandledScreen();
            mc.setScreen(new InventoryScreen(mc.player));
        }
        int repetitions = (int) NativeBridge.number(params, "count", 1);
        String output = NativeBridge.itemName(recipe.value().getResult(mc.world.getRegistryManager()));
        int yield = recipe.value().getResult(mc.world.getRegistryManager()).getCount();
        int before = count(output);
        return new NativeBridge.Job() {
            int stage, completed, expected;
            long waitUntil = System.nanoTime() + 200_000_000L;
            long progress = System.nanoTime();
            public JsonObject step() {
                if (System.nanoTime() < waitUntil) return null;
                if (System.nanoTime() - progress > 3_000_000_000L) return NativeBridge.fail("Crafting did not progress; partial effects persist");
                ScreenHandler handler = mc.player.currentScreenHandler;
                if (table ? !(handler instanceof CraftingScreenHandler) : handler != mc.player.playerScreenHandler) return null;
                if (stage == 0) {
                    if (completed == repetitions) return NativeBridge.ok("crafted_count", count(output) - before);
                    if (!craftable(recipe.value())) return NativeBridge.fail("Insufficient ingredients for remaining recipe executions");
                    expected = count(output) + yield;
                    mc.interactionManager.clickRecipe(handler.syncId, recipe, false);
                    stage = 1; waitUntil = System.nanoTime() + 200_000_000L;
                } else if (stage == 1) {
                    ItemStack result = handler.getSlot(0).getStack();
                    if (result.isEmpty() || !NativeBridge.itemName(result).equals(output)) return null;
                    click(0, 0, SlotActionType.QUICK_MOVE);
                    stage = 2; waitUntil = System.nanoTime() + 200_000_000L;
                } else if (count(output) >= expected) {
                    completed++; stage = 0; progress = System.nanoTime();
                    waitUntil = System.nanoTime() + 200_000_000L;
                }
                return null;
            }
        };
    }

    private static boolean deposit(Ingredient ingredient, int amount, int destination) {
        var player = NativeBridge.client().player;
        if (!player.currentScreenHandler.getCursorStack().isEmpty()) return false;
        int remaining = amount;
        for (Slot slot : player.currentScreenHandler.slots) {
            if (slot.inventory != player.getInventory() || !ingredient.test(slot.getStack())) continue;
            int take = Math.min(slot.getStack().getCount(), remaining);
            if (take == 0) continue;
            click(slot.id, 0, SlotActionType.PICKUP);
            for (int i = 0; i < take; i++) click(destination, 1, SlotActionType.PICKUP);
            if (!player.currentScreenHandler.getCursorStack().isEmpty()) click(slot.id, 0, SlotActionType.PICKUP);
            remaining -= take;
            if (remaining == 0) return true;
        }
        return false;
    }

    static NativeBridge.Job smelt(JsonObject params) {
        var mc = NativeBridge.client();
        String output = NativeBridge.text(params, "output_item", "").replace("minecraft:", "");
        var recipes = mc.world.getRecipeManager().listAllOfType(RecipeType.SMELTING).stream()
                .filter(entry -> NativeBridge.itemName(entry.value().getResult(mc.world.getRegistryManager())).equals(output))
                .sorted(Comparator.comparing(entry -> entry.id().toString())).toList();
        int amount = (int) NativeBridge.number(params, "count", 1);
        int index = params.has("recipe_index") ? params.get("recipe_index").getAsInt() : -1;
        if (!params.has("recipe_index")) {
            for (int i = 0; i < recipes.size(); i++) {
                Ingredient candidate = recipes.get(i).value().getIngredients().get(0);
                int have = 0;
                for (int slot = 0; slot < 36; slot++) {
                    ItemStack stack = mc.player.getInventory().getStack(slot);
                    if (candidate.test(stack)) have += stack.getCount();
                }
                if (have >= amount) { index = i; break; }
            }
        }
        if (index < 0 || index >= recipes.size()) return () -> NativeBridge.fail("Smelting recipe not found");
        var recipe = recipes.get(index).value();
        Ingredient input = recipe.getIngredients().get(0);
        int available = 0;
        for (int i = 0; i < 36; i++) if (input.test(mc.player.getInventory().getStack(i))) available += mc.player.getInventory().getStack(i).getCount();
        if (available < amount) return () -> NativeBridge.fail("Insufficient smelting input");
        Map<Item, Integer> fuels = AbstractFurnaceBlockEntity.createFuelTimeMap();
        Item fuel = null;
        int fuelCount = 0;
        for (int i = 0; i < 36; i++) {
            ItemStack stack = mc.player.getInventory().getStack(i);
            Integer duration = fuels.get(stack.getItem());
            if (duration == null || input.test(stack)) continue;
            int needed = (int) Math.ceil((double) (amount * recipe.getCookingTime()) / duration);
            if (count(NativeBridge.itemName(stack)) >= needed) { fuel = stack.getItem(); fuelCount = needed; break; }
        }
        if (fuel == null) return () -> NativeBridge.fail("Insufficient supported fuel distinct from input");
        if (!openStation("furnace")) return () -> NativeBridge.fail("Aim at a reachable furnace first");
        Ingredient selectedFuel = Ingredient.ofItems(fuel);
        int selectedFuelCount = fuelCount, before = count(output);
        return new NativeBridge.Job() {
            int stage;
            long next = System.nanoTime() + 250_000_000L;
            public JsonObject step() {
                if (System.nanoTime() < next) return null;
                if (!(mc.player.currentScreenHandler instanceof FurnaceScreenHandler furnace)) return null;
                if (stage == 0) {
                    if (!furnace.getSlot(0).getStack().isEmpty() || !furnace.getSlot(1).getStack().isEmpty()
                            || !furnace.getSlot(2).getStack().isEmpty()) return NativeBridge.fail("Furnace must initially be empty");
                    if (!deposit(input, amount, 0) || !deposit(selectedFuel, selectedFuelCount, 1))
                        return NativeBridge.fail("Could not insert furnace contents; partial contents remain");
                    stage = 1;
                } else if (stage == 1) {
                    ItemStack result = furnace.getSlot(2).getStack();
                    if (result.getCount() >= amount && NativeBridge.itemName(result).equals(output)) {
                        click(2, 0, SlotActionType.QUICK_MOVE);
                        stage = 2; next = System.nanoTime() + 250_000_000L;
                    }
                } else if (count(output) - before >= amount) {
                    return NativeBridge.ok("smelted_count", count(output) - before);
                }
                return null;
            }
        };
    }
}
