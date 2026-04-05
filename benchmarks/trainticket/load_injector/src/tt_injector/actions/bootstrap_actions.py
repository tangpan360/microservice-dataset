from __future__ import annotations

import time

from tt_injector.actions.order_actions import collect_ticket, pay_order, preserve_ticket, query_orders
from tt_injector.core.auth import AuthSession
from tt_injector.core.http import HttpClient
from tt_injector.core.models import OrderRecord, PreserveOptions


def _travel_day(order: OrderRecord) -> str | None:
    travel_date = order.raw.get("travelDate")
    if travel_date is None:
        return None
    try:
        return time.strftime("%Y-%m-%d", time.localtime(travel_date / 1000))
    except (TypeError, ValueError, OSError):
        return None


def _match_existing_orders(orders: list[OrderRecord], options: PreserveOptions) -> list[OrderRecord]:
    matched = []
    for order in orders:
        if options.preferred_trip_id and order.trip_id != options.preferred_trip_id:
            continue
        if order.from_station and order.from_station != options.start:
            continue
        if order.to_station and order.to_station != options.end:
            continue
        order_day = _travel_day(order)
        if order_day is not None and order_day != options.date:
            continue
        matched.append(order)
    matched.sort(key=lambda item: item.raw.get("boughtDate") or 0, reverse=True)
    return matched


def ensure_order(
    client: HttpClient,
    auth: AuthSession,
    *,
    required_status: str,
    options: PreserveOptions,
    rng,
) -> OrderRecord | None:
    query_other = not options.high_speed

    if not options.force_new_order:
        if required_status == "unpaid":
            existing = query_orders(client, auth, query_other=query_other, statuses={0})
            orders = _match_existing_orders(existing.payload.get("orders") or [], options)
            if orders:
                return orders[0]
        elif required_status == "paid":
            existing = query_orders(client, auth, query_other=query_other, statuses={1})
            orders = _match_existing_orders(existing.payload.get("orders") or [], options)
            if orders:
                return orders[0]
        elif required_status == "collected":
            existing = query_orders(client, auth, query_other=query_other, statuses={2})
            orders = _match_existing_orders(existing.payload.get("orders") or [], options)
            if orders:
                return orders[0]

    preserved = preserve_ticket(client, auth, options, rng)
    if not preserved.ok:
        return None

    trip_id = preserved.payload.get("trip_id")
    for _ in range(5):
        current = query_orders(client, auth, query_other=query_other, statuses={0, 1, 2, 3, 4, 5, 6})
        orders = current.payload.get("orders") or []
        matched = _match_existing_orders(
            orders,
            PreserveOptions(
                start=options.start,
                end=options.end,
                date=options.date,
                high_speed=options.high_speed,
                preferred_trip_id=trip_id,
            ),
        )
        if matched:
            order = matched[0]
            break
        time.sleep(1)
    else:
        return None

    if required_status in {"paid", "collected"} and order.status == 0:
        paid = pay_order(client, auth, order)
        if not paid.ok:
            return None
        order = OrderRecord(
            order_id=order.order_id,
            trip_id=order.trip_id,
            status=1,
            account_id=order.account_id,
            from_station=order.from_station,
            to_station=order.to_station,
            raw=order.raw,
        )

    if required_status == "collected" and order.status == 1:
        collected = collect_ticket(client, auth, order)
        if not collected.ok:
            return None
        order = OrderRecord(
            order_id=order.order_id,
            trip_id=order.trip_id,
            status=2,
            account_id=order.account_id,
            from_station=order.from_station,
            to_station=order.to_station,
            raw=order.raw,
        )

    return order
