"""Private, immutable native FinishedTrade receipts across later cancellations."""

from copy import deepcopy


class MarketTradeJournal:
    def __init__(self, journal):
        self.journal = journal
        self.events = []

    def write(self, **row):
        self.journal.write(**row)
        event = row.get("event", {})
        if row.get("origin") == "native_event" and event.get("event") == "trade_complete":
            self.events.append(deepcopy({"actor": row["actor"], "event": event}))

    def close(self):
        self.journal.close()

    def snapshot(self, observation, registry=None):
        session = observation["session_id"]
        through = observation["event_cursor"]
        if (type(through) is not int or through < 0
                or observation["sequence_domain"] != {
                    "kind": "client-update-counter", "session_id": session}):
            raise ValueError("Invalid native market event cursor")
        if registry is None:
            registry = {"session_id": session, "actor": deepcopy(observation["control_actor"]),
                        "opening_sequence": through}
        if registry["session_id"] != session or through < registry["opening_sequence"]:
            raise ValueError("Native market event session or boundary changed")
        events = [row["event"] for row in self.events
                  if row["actor"] == session
                  and registry["opening_sequence"] < row["event"]["seq"] <= through]
        return deepcopy({"schema": "livequest-native-market-trades/1", "registry": registry,
                         "through_sequence": through, "events": events})


def trade_receipts(initial, final):
    first, last = (state["private_market_evidence"]["trade_history"]
                   for state in (initial, final))
    registry = first["registry"]
    opening = registry["opening_sequence"]
    if (first["schema"] != "livequest-native-market-trades/1"
            or last["schema"] != first["schema"] or last["registry"] != registry
            or registry["actor"] != initial["control_actor"]
            or registry["session_id"] != initial["session_id"]
            or final["session_id"] != initial["session_id"]
            or type(opening) is not int or opening < 0
            or first["events"] or first["through_sequence"] != opening
            or first["through_sequence"] != initial["event_cursor"]
            or last["through_sequence"] != final["event_cursor"]
            or type(last["through_sequence"]) is not int
            or last["through_sequence"] < opening):
        raise ValueError("Invalid immutable native market trade history")
    previous = opening
    receipts = []
    for event in last["events"]:
        if (event["type"] != "event" or event["event"] != "trade_complete"
                or event["protocol_version"] != "0.2"
                or event["session_id"] != registry["session_id"]
                or event["sequence_domain"] != {
                    "kind": "client-update-counter", "session_id": registry["session_id"]}
                or type(event["seq"]) is not int
                or not previous < event["seq"] <= last["through_sequence"]):
            raise ValueError("Invalid native market trade event identity or order")
        previous = event["seq"]
        receipts.append(event["data"])
    return receipts
