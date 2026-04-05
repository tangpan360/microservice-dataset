from __future__ import annotations

import time
from random import Random

from tt_injector.actions.admin_actions import query_admin_basic_config, query_admin_basic_price
from tt_injector.actions.bootstrap_actions import ensure_order
from tt_injector.actions.order_actions import cancel_order, consign_order, enter_station, pay_order, query_orders, rebook_order
from tt_injector.actions.query_actions import (
    pick_trip_id,
    query_advanced_plan,
    query_contacts,
    query_food,
    query_route,
    search_parallel_tickets,
    search_tickets,
)
from tt_injector.core.helpers import random_bool
from tt_injector.core.models import ActionResult, PreserveOptions, TicketQuery
from tt_injector.scenarios.runtime import ScenarioRuntime


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _tomorrow() -> str:
    return time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400))


def _browse_query(rng: Random) -> TicketQuery:
    if random_bool(rng):
        return TicketQuery(start="Shang Hai", end="Su Zhou", date=_today(), high_speed=True)
    return TicketQuery(start="Shang Hai", end="Nan Jing", date=_today(), high_speed=False)


def _preserve_options(rng: Random) -> PreserveOptions:
    if random_bool(rng):
        return PreserveOptions(
            start="Shang Hai",
            end="Su Zhou",
            date=_today(),
            high_speed=True,
            need_food=False,
            need_assurance=random_bool(rng),
            need_consign=False,
        )
    return PreserveOptions(
        start="Shang Hai",
        end="Nan Jing",
        date=_today(),
        high_speed=False,
        need_food=False,
        need_assurance=random_bool(rng),
        need_consign=False,
    )


def _normal_preserve_options() -> PreserveOptions:
    return PreserveOptions(
        start="Shang Hai",
        end="Nan Jing",
        date=_today(),
        high_speed=False,
        need_food=False,
        need_assurance=False,
        need_consign=False,
    )


def browse_basic(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    return search_tickets(runtime.client, runtime.user_auth, _browse_query(rng))


def browse_plus_route(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    route_result = query_route(runtime.client, runtime.user_auth, "92708982-77af-4318-be25-57ccb0ff69ad")
    if not route_result.ok:
        return route_result
    query = TicketQuery(start="Su Zhou", end="Shang Hai", date=_today(), high_speed=True)
    ticket_result = search_parallel_tickets(runtime.client, runtime.user_auth, query)
    if not ticket_result.ok:
        return ticket_result
    trip_id = pick_trip_id(ticket_result, rng) or "D1345"
    return query_food(runtime.client, runtime.user_auth, date=_today(), start="Su Zhou", end="Shang Hai", trip_id=trip_id)


def preserve_and_pay(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    options = _preserve_options(rng)
    order = ensure_order(runtime.client, runtime.user_auth, required_status="unpaid", options=options, rng=rng)
    if order is None:
        return ActionResult(ok=False, name="preserveAndPay", detail="无法创建未支付订单")
    return pay_order(runtime.client, runtime.user_auth, order)


def pay_collect_enter(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    options = PreserveOptions(
        start="Shang Hai",
        end="Nan Jing",
        date=_today(),
        high_speed=False,
        need_food=False,
        need_assurance=False,
        need_consign=False,
    )
    order = ensure_order(runtime.client, runtime.user_auth, required_status="collected", options=options, rng=rng)
    if order is None:
        return ActionResult(ok=False, name="payCollectEnter", detail="无法准备已取票订单")
    return enter_station(runtime.client, runtime.user_auth, order)


def cancel_flow(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    options = PreserveOptions(
        start="Shang Hai",
        end="Nan Jing",
        date=_today(),
        high_speed=False,
        need_food=False,
        need_assurance=False,
        need_consign=False,
    )
    order = ensure_order(runtime.client, runtime.user_auth, required_status="unpaid", options=options, rng=rng)
    if order is None:
        return ActionResult(ok=False, name="cancelFlow", detail="无法准备可取消订单")
    return cancel_order(runtime.client, runtime.user_auth, order)


def rebook_flow(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    date = _tomorrow()
    ticket_result = search_tickets(
        runtime.client,
        runtime.user_auth,
        TicketQuery(start="Nan Jing", end="Shang Hai", date=date, high_speed=True),
    )
    trip_ids = ticket_result.payload.get("trip_ids") or []
    if len(trip_ids) < 2:
        return ActionResult(ok=False, name="rebookFlow", detail="可改签候选车次不足")
    old_trip_id = trip_ids[0]
    new_trip_id = trip_ids[1]
    options = PreserveOptions(
        start="Nan Jing",
        end="Shang Hai",
        date=date,
        high_speed=True,
        preferred_trip_id=old_trip_id,
        need_food=False,
        need_assurance=False,
        need_consign=False,
    )
    order = ensure_order(runtime.client, runtime.user_auth, required_status="paid", options=options, rng=rng)
    if order is None:
        return ActionResult(ok=False, name="rebookFlow", detail="无法准备可改签订单")
    return rebook_order(runtime.client, runtime.user_auth, order=order, new_trip_id=new_trip_id, date=date, seat_type="2")


def consign_flow(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    options = PreserveOptions(
        start="Shang Hai",
        end="Nan Jing",
        date=_today(),
        high_speed=False,
        need_food=False,
        need_assurance=False,
        need_consign=False,
    )
    order = ensure_order(runtime.client, runtime.user_auth, required_status="unpaid", options=options, rng=rng)
    if order is None:
        return ActionResult(ok=False, name="consignFlow", detail="无法准备托运订单")
    return consign_order(runtime.client, runtime.user_auth, order)


def admin_observe(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    config_result = query_admin_basic_config(runtime.client, runtime.admin_auth)
    if not config_result.ok:
        return config_result
    return query_admin_basic_price(runtime.client, runtime.admin_auth)


def browse_advanced(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    plan_type = "cheapest" if random_bool(rng) else "quickest"
    return query_advanced_plan(
        runtime.client,
        runtime.user_auth,
        date=_today(),
        start="Nan Jing",
        end="Shang Hai",
        plan_type=plan_type,
    )


def browse_advanced_alt(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    plan_type = "minStation" if random_bool(rng) else "quickest"
    return query_advanced_plan(
        runtime.client,
        runtime.user_auth,
        date=_today(),
        start="Shang Hai",
        end="Nan Jing",
        plan_type=plan_type,
    )


def order_refresh(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    query_other = random_bool(rng)
    return query_orders(runtime.client, runtime.user_auth, query_other=query_other, statuses={0, 1, 2, 3, 4, 5, 6})


def contact_lookup(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    return query_contacts(runtime.client, runtime.user_auth)


def preserve_with_food(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    options = PreserveOptions(
        start="Shang Hai",
        end="Su Zhou",
        date=_today(),
        high_speed=True,
        need_food=True,
        need_assurance=False,
        need_consign=False,
        force_new_order=True,
    )
    order = ensure_order(runtime.client, runtime.user_auth, required_status="unpaid", options=options, rng=rng)
    if order is None:
        return ActionResult(ok=False, name="preserveWithFood", detail="无法创建带餐食订单")
    return pay_order(runtime.client, runtime.user_auth, order)


def preserve_with_assurance(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    options = PreserveOptions(
        start="Shang Hai",
        end="Nan Jing",
        date=_today(),
        high_speed=False,
        need_food=False,
        need_assurance=True,
        need_consign=False,
        force_new_order=True,
    )
    order = ensure_order(runtime.client, runtime.user_auth, required_status="unpaid", options=options, rng=rng)
    if order is None:
        return ActionResult(ok=False, name="preserveWithAssurance", detail="无法创建带保险订单")
    return pay_order(runtime.client, runtime.user_auth, order)


def food_browse_only(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    ticket_result = search_parallel_tickets(
        runtime.client,
        runtime.user_auth,
        TicketQuery(start="Su Zhou", end="Shang Hai", date=_today(), high_speed=True),
    )
    if not ticket_result.ok:
        return ticket_result
    trip_id = pick_trip_id(ticket_result, rng) or "D1345"
    return query_food(runtime.client, runtime.user_auth, date=_today(), start="Su Zhou", end="Shang Hai", trip_id=trip_id)


def post_purchase_order_view(runtime: ScenarioRuntime, rng: Random) -> ActionResult:
    options = _normal_preserve_options()
    order = ensure_order(runtime.client, runtime.user_auth, required_status="paid", options=options, rng=rng)
    if order is None:
        return ActionResult(ok=False, name="postPurchaseOrderView", detail="无法准备已支付订单")
    query_other = not options.high_speed
    return query_orders(runtime.client, runtime.user_auth, query_other=query_other, statuses={0, 1, 2, 3, 4, 5, 6})
