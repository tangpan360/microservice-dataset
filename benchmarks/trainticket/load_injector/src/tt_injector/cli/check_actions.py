from __future__ import annotations

import json
import time

from tt_injector.actions.admin_actions import query_admin_basic_config, query_admin_basic_price
from tt_injector.actions.bootstrap_actions import ensure_order
from tt_injector.actions.order_actions import (
    cancel_order,
    collect_ticket,
    consign_order,
    enter_station,
    pay_order,
    preserve_ticket,
    query_orders,
    rebook_order,
)
from tt_injector.actions.query_actions import (
    query_advanced_plan,
    query_assurance_types,
    query_contacts,
    query_food,
    query_route,
    search_parallel_tickets,
    search_tickets,
)
from tt_injector.core.context import RuntimeContext
from tt_injector.core.models import ActionResult, PreserveOptions, TicketQuery
from tt_injector.scenarios.runtime import ScenarioRuntime


def today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def tomorrow() -> str:
    return time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400))


def summarize(result: ActionResult | None, action: str, elapsed_ms: int, *, detail: str | None = None, payload_keys: list[str] | None = None) -> dict:
    if result is None:
        return {
            "action": action,
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "detail": detail or "no result",
            "payload_keys": payload_keys or [],
        }
    return {
        "action": action,
        "ok": bool(result.ok),
        "elapsed_ms": elapsed_ms,
        "detail": (result.detail or "")[:240],
        "payload_keys": sorted(list((result.payload or {}).keys())),
    }


def main() -> int:
    context = RuntimeContext()
    runtime = ScenarioRuntime.create(context)
    rng = context.new_rng()
    client = runtime.client
    user_auth = runtime.user_auth
    admin_auth = runtime.admin_auth
    results: list[dict] = []

    def run(action: str, fn):
        started = time.time()
        try:
            result = fn()
            elapsed_ms = int((time.time() - started) * 1000)
            results.append(summarize(result, action, elapsed_ms))
            return result
        except Exception as exc:
            elapsed_ms = int((time.time() - started) * 1000)
            results.append(
                {
                    "action": action,
                    "ok": False,
                    "elapsed_ms": elapsed_ms,
                    "detail": f"{type(exc).__name__}: {str(exc)[:240]}",
                    "payload_keys": [],
                }
            )
            return None

    hs_query = TicketQuery(start="Shang Hai", end="Su Zhou", date=today(), high_speed=True)
    normal_query = TicketQuery(start="Shang Hai", end="Nan Jing", date=today(), high_speed=False)
    rebook_query = TicketQuery(start="Nan Jing", end="Shang Hai", date=tomorrow(), high_speed=True)

    hs_tickets = run("search_tickets_high_speed", lambda: search_tickets(client, user_auth, hs_query))
    normal_tickets = run("search_tickets_normal", lambda: search_tickets(client, user_auth, normal_query))
    parallel_tickets = run(
        "search_parallel_tickets",
        lambda: search_parallel_tickets(client, user_auth, TicketQuery(start="Su Zhou", end="Shang Hai", date=today(), high_speed=True)),
    )
    run("query_route", lambda: query_route(client, user_auth, "92708982-77af-4318-be25-57ccb0ff69ad"))
    run("query_contacts", lambda: query_contacts(client, user_auth))
    run("query_assurance_types", lambda: query_assurance_types(client, user_auth))
    run(
        "query_advanced_plan_cheapest",
        lambda: query_advanced_plan(client, user_auth, date=today(), start="Nan Jing", end="Shang Hai", plan_type="cheapest"),
    )
    run(
        "query_advanced_plan_quickest",
        lambda: query_advanced_plan(client, user_auth, date=today(), start="Nan Jing", end="Shang Hai", plan_type="quickest"),
    )

    food_trip = None
    if parallel_tickets and parallel_tickets.ok:
        food_trip = (parallel_tickets.payload.get("trip_ids") or [None])[0]
    if food_trip is None and hs_tickets and hs_tickets.ok:
        food_trip = (hs_tickets.payload.get("trip_ids") or [None])[0]
    if food_trip:
        run("query_food", lambda: query_food(client, user_auth, date=today(), start="Su Zhou", end="Shang Hai", trip_id=food_trip))
    else:
        results.append({"action": "query_food", "ok": False, "elapsed_ms": 0, "detail": "no available trip id for food query", "payload_keys": []})

    paid_order = ensure_order(
        client,
        user_auth,
        required_status="paid",
        options=PreserveOptions(start="Shang Hai", end="Nan Jing", date=today(), high_speed=False),
        rng=rng,
    )
    results.append({"action": "ensure_order_paid", "ok": paid_order is not None, "elapsed_ms": 0, "detail": "prepared paid order" if paid_order else "failed to prepare paid order", "payload_keys": ["order"] if paid_order else []})

    collected_order = ensure_order(
        client,
        user_auth,
        required_status="collected",
        options=PreserveOptions(start="Shang Hai", end="Nan Jing", date=today(), high_speed=False),
        rng=rng,
    )
    results.append({"action": "ensure_order_collected", "ok": collected_order is not None, "elapsed_ms": 0, "detail": "prepared collected order" if collected_order else "failed to prepare collected order", "payload_keys": ["order"] if collected_order else []})

    unpaid_order = ensure_order(
        client,
        user_auth,
        required_status="unpaid",
        options=PreserveOptions(start="Shang Hai", end="Nan Jing", date=today(), high_speed=False),
        rng=rng,
    )
    results.append({"action": "ensure_order_unpaid", "ok": unpaid_order is not None, "elapsed_ms": 0, "detail": "prepared unpaid order" if unpaid_order else "failed to prepare unpaid order", "payload_keys": ["order"] if unpaid_order else []})

    run("query_orders_normal_any", lambda: query_orders(client, user_auth, query_other=False, statuses={0, 1, 2, 3, 4, 5, 6}))
    run("query_orders_other_any", lambda: query_orders(client, user_auth, query_other=True, statuses={0, 1, 2, 3, 4, 5, 6}))
    run("preserve_ticket_normal", lambda: preserve_ticket(client, user_auth, PreserveOptions(start="Shang Hai", end="Nan Jing", date=today(), high_speed=False), rng))
    run("preserve_ticket_high_speed", lambda: preserve_ticket(client, user_auth, PreserveOptions(start="Shang Hai", end="Su Zhou", date=today(), high_speed=True), rng))
    run(
        "preserve_ticket_with_food",
        lambda: preserve_ticket(
            client,
            user_auth,
            PreserveOptions(
                start="Shang Hai",
                end="Su Zhou",
                date=today(),
                high_speed=True,
                need_food=True,
                force_new_order=True,
            ),
            rng,
        ),
    )
    run(
        "preserve_ticket_with_assurance",
        lambda: preserve_ticket(
            client,
            user_auth,
            PreserveOptions(
                start="Shang Hai",
                end="Nan Jing",
                date=today(),
                high_speed=False,
                need_assurance=True,
                force_new_order=True,
            ),
            rng,
        ),
    )

    if unpaid_order is not None:
        run("pay_order", lambda: pay_order(client, user_auth, unpaid_order))
        run("cancel_order", lambda: cancel_order(client, user_auth, unpaid_order))
    else:
        results.append({"action": "pay_order", "ok": False, "elapsed_ms": 0, "detail": "no unpaid order", "payload_keys": []})
        results.append({"action": "cancel_order", "ok": False, "elapsed_ms": 0, "detail": "no unpaid order", "payload_keys": []})

    if paid_order is not None:
        run("collect_ticket", lambda: collect_ticket(client, user_auth, paid_order))
        run("consign_order", lambda: consign_order(client, user_auth, paid_order))
    else:
        results.append({"action": "collect_ticket", "ok": False, "elapsed_ms": 0, "detail": "no paid order", "payload_keys": []})
        results.append({"action": "consign_order", "ok": False, "elapsed_ms": 0, "detail": "no paid order", "payload_keys": []})

    if collected_order is not None:
        run("enter_station", lambda: enter_station(client, user_auth, collected_order))
    else:
        results.append({"action": "enter_station", "ok": False, "elapsed_ms": 0, "detail": "no collected order", "payload_keys": []})

    rebook_tickets = run("search_tickets_rebook_candidates", lambda: search_tickets(client, user_auth, rebook_query))
    if rebook_tickets and rebook_tickets.ok and len(rebook_tickets.payload.get("trip_ids") or []) >= 2:
        trip_ids = rebook_tickets.payload["trip_ids"]
        old_trip_id = trip_ids[0]
        new_trip_id = trip_ids[1]
        rebook_order_record = ensure_order(
            client,
            user_auth,
            required_status="paid",
            options=PreserveOptions(
                start="Nan Jing",
                end="Shang Hai",
                date=tomorrow(),
                high_speed=True,
                preferred_trip_id=old_trip_id,
            ),
            rng=rng,
        )
        results.append({"action": "ensure_order_rebook_paid", "ok": rebook_order_record is not None, "elapsed_ms": 0, "detail": "prepared rebook order" if rebook_order_record else "failed to prepare rebook order", "payload_keys": ["order"] if rebook_order_record else []})
        if rebook_order_record is not None:
            run("rebook_order", lambda: rebook_order(client, user_auth, order=rebook_order_record, new_trip_id=new_trip_id, date=tomorrow(), seat_type="2"))
        else:
            results.append({"action": "rebook_order", "ok": False, "elapsed_ms": 0, "detail": "no paid order for rebook", "payload_keys": []})
    else:
        results.append({"action": "rebook_order", "ok": False, "elapsed_ms": 0, "detail": "not enough rebook candidates", "payload_keys": []})

    run("query_admin_basic_config", lambda: query_admin_basic_config(client, admin_auth))
    run("query_admin_basic_price", lambda: query_admin_basic_price(client, admin_auth))

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(item["ok"] for item in results if item["action"] != "rebook_order") else 1


if __name__ == "__main__":
    raise SystemExit(main())
