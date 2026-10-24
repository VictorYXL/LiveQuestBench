package org.livequestbench;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.minecraft.item.ItemStack;
import net.minecraft.network.packet.c2s.play.SelectMerchantTradeC2SPacket;
import net.minecraft.screen.MerchantScreenHandler;
import net.minecraft.screen.slot.SlotActionType;
import net.minecraft.util.Hand;
import net.minecraft.util.hit.EntityHitResult;
import net.minecraft.village.Merchant;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

final class NativeTrading {
    private static String quote(MerchantScreenHandler handler, int index) {
        String value = handler.syncId + ":" + index + ":" + handler.getRecipes().get(index).toNbt();
        return UUID.nameUUIDFromBytes(value.getBytes(StandardCharsets.UTF_8)).toString();
    }

    static NativeBridge.Job inspect() {
        var mc = NativeBridge.client();
        if (!(mc.player.currentScreenHandler instanceof MerchantScreenHandler)) {
            if (mc.currentScreen != null) mc.player.closeHandledScreen();
            if (!(mc.crosshairTarget instanceof EntityHitResult hit)
                    || !(hit.getEntity() instanceof Merchant) || !hit.getEntity().isAlive()
                    || mc.player.getEyePos().squaredDistanceTo(hit.getPos()) > 9)
                return () -> NativeBridge.fail("Aim at a living merchant within three-block native reach");
            if (!mc.interactionManager.interactEntity(mc.player, hit.getEntity(), Hand.MAIN_HAND).isAccepted())
                return () -> NativeBridge.fail("Native merchant interaction refused");
        }
        long started = System.nanoTime();
        return () -> {
            if (!(mc.player.currentScreenHandler instanceof MerchantScreenHandler handler)
                    || handler.getRecipes().isEmpty())
                return System.nanoTime() - started > 3_000_000_000L
                        ? NativeBridge.fail("Native merchant offers did not arrive") : null;
            JsonArray offers = new JsonArray();
            for (int index = 0; index < handler.getRecipes().size(); index++) {
                var offer = handler.getRecipes().get(index);
                offers.add(NativeBridge.object(
                        "offer_index", index, "quote", quote(handler, index),
                        "buy", NativeBridge.item(offer.getAdjustedFirstBuyItem(), 0),
                        "second_buy", offer.getSecondBuyItem().isEmpty() ? null
                                : NativeBridge.item(offer.getSecondBuyItem(), 1),
                        "sell", NativeBridge.item(offer.getSellItem(), 2),
                        "uses", offer.getUses(), "max_uses", offer.getMaxUses(),
                        "disabled", offer.isDisabled()));
            }
            JsonArray inputs = new JsonArray();
            for (int slot = 0; slot < 2; slot++)
                inputs.add(NativeBridge.item(handler.getSlot(slot).getStack(), slot));
            return NativeBridge.ok("offers", offers, "payment_slots", inputs,
                    "cursor", handler.getCursorStack().isEmpty() ? null
                            : NativeBridge.item(handler.getCursorStack(), -1));
        };
    }

    static NativeBridge.Job trade(JsonObject params) {
        var mc = NativeBridge.client();
        if (!(mc.player.currentScreenHandler instanceof MerchantScreenHandler handler))
            return () -> NativeBridge.fail("Inspect a merchant before trading");
        int index = params.get("offer_index").getAsInt();
        if (index < 0 || index >= handler.getRecipes().size()
                || !quote(handler, index).equals(params.get("quote").getAsString()))
            return () -> NativeBridge.fail("Offer quote is stale or invalid; inspect the open merchant again");
        var offer = handler.getRecipes().get(index);
        if (offer.isDisabled() || !handler.getCursorStack().isEmpty())
            return () -> NativeBridge.fail("Offer is exhausted or inventory cursor is occupied");
        int destinationIndex = params.get("slot").getAsInt() - 1;
        var destination = handler.slots.stream().filter(slot -> slot.inventory == mc.player.getInventory()
                && slot.getIndex() == destinationIndex).findFirst().orElse(null);
        if (destinationIndex < 0 || destinationIndex > 8 || destination == null || destination.hasStack())
            return () -> NativeBridge.fail("Choose an empty hotbar slot 1-9 for the purchased stack");
        String output = NativeBridge.itemName(offer.getSellItem());
        int before = NativeInventory.count(output), amount = offer.getSellItem().getCount();
        handler.setRecipeIndex(index);
        handler.switchTo(index);
        mc.getNetworkHandler().sendPacket(new SelectMerchantTradeC2SPacket(index));
        long started = System.nanoTime();
        return new NativeBridge.Job() {
            int stage;
            long submitted;
            public JsonObject step() {
                if (mc.player.currentScreenHandler != handler)
                    return NativeBridge.fail("Merchant screen closed; applied trade effects persist");
                if (System.nanoTime() - started > 3_000_000_000L)
                    return NativeBridge.fail("Trade did not complete; inspect inventory and cursor for partial effects");
                if (stage == 0) {
                    if (System.nanoTime() - started < 200_000_000L) return null;
                    var result = handler.getSlot(2).getStack();
                    if (result.isEmpty() || !ItemStack.areEqual(result, offer.getSellItem())) return null;
                    if (destination.hasStack() || !handler.getCursorStack().isEmpty())
                        return NativeBridge.fail("Purchase destination or cursor changed before exchange");
                    // PICKUP commits one exchange; shift-clicking output can repeat the trade.
                    NativeInventory.click(2, 0, SlotActionType.PICKUP);
                    if (!ItemStack.areEqual(handler.getCursorStack(), offer.getSellItem()))
                        return NativeBridge.fail("Native output pickup was not confirmed; inspect partial effects");
                    NativeInventory.click(destination.id, 0, SlotActionType.PICKUP);
                    submitted = System.nanoTime();
                    stage = 1;
                } else if (System.nanoTime() - submitted >= 250_000_000L
                        && handler.getCursorStack().isEmpty() && ItemStack.areEqual(destination.getStack(), offer.getSellItem())
                        && NativeInventory.count(output) == before + amount) {
                    return NativeBridge.ok("exchanges", 1, "received_item", output, "received_count", amount,
                            "slot", destinationIndex + 1);
                }
                return null;
            }
        };
    }
}
