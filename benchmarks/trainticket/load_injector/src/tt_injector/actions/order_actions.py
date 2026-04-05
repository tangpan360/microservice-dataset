from __future__ import annotations

import time

from tt_injector.actions.query_actions import query_contacts, search_tickets
from tt_injector.core.auth import AuthSession
from tt_injector.core.helpers import random_phone, random_pick, random_text
from tt_injector.core.http import HttpClient
from tt_injector.core.models import ActionResult, OrderRecord, PreserveOptions, TicketQuery


def query_orders(client: HttpClient, auth: AuthSession, *, query_other: bool, statuses: set[int] | None = None) -> ActionResult:
    path = "/api/v1/orderOtherService/orderOther/refresh" if query_other else "/api/v1/orderservice/order/refresh"
    response = client.request(
        "POST",
        path,
        headers=auth.headers(),
        json_data={"loginId": auth.user_id},
    )
    body = response.body or {}
    data = body.get("data") or []
    records: list[OrderRecord] = []
    for item in data:
        status = item.get("status")
        if statuses is not None and status not in statuses:
            continue
        records.append(
            OrderRecord(
                order_id=item.get("id", ""),
                trip_id=item.get("trainNumber", ""),
                status=status,
                account_id=item.get("accountId"),
                from_station=item.get("from"),
                to_station=item.get("to"),
                raw=item,
            )
        )
    return ActionResult(ok=bool(records), name="queryOrders", detail=response.text, payload={"orders": records})


def preserve_ticket(client: HttpClient, auth: AuthSession, options: PreserveOptions, rng) -> ActionResult:
    ticket_result = search_tickets(
        client,
        auth,
        TicketQuery(start=options.start, end=options.end, date=options.date, high_speed=options.high_speed),
    )
    if not ticket_result.ok:
        return ActionResult(ok=False, name="preserveTicket", detail=ticket_result.detail)

    contacts_result = query_contacts(client, auth)
    if not contacts_result.ok:
        return ActionResult(ok=False, name="preserveTicket", detail=contacts_result.detail)

    trip_ids = ticket_result.payload["trip_ids"]
    trip_id = options.preferred_trip_id if options.preferred_trip_id in trip_ids else random_pick(rng, trip_ids)
    contact_id = random_pick(rng, contacts_result.payload["contact_ids"])
    path = "/api/v1/preserveservice/preserve" if options.high_speed else "/api/v1/preserveotherservice/preserveOther"
    payload = {
        "accountId": auth.user_id,
        "assurance": 1 if options.need_assurance else "0",
        "contactsId": contact_id,
        "date": options.date,
        "from": options.start,
        "to": options.end,
        "tripId": trip_id,
        "foodType": "0",
        "seatType": "2" if options.high_speed else "3",
    }
    if options.need_food:
        payload.update(
            {
                "foodName": "Soup",
                "foodPrice": 3.7,
                "foodType": 2,
                "stationName": "Su Zhou",
                "storeName": "Roman Holiday",
            }
        )
    if options.need_consign:
        payload.update(
            {
                "consigneeName": random_text(rng),
                "consigneePhone": random_phone(rng),
                "consigneeWeight": rng.randint(1, 10),
                "handleDate": options.date,
            }
        )

    response = client.request("POST", path, headers=auth.headers(), json_data=payload)
    body = response.body or {}
    ok = response.status_code == 200 and body.get("status") == 1
    return ActionResult(ok=ok, name="preserveTicket", detail=response.text, payload={"trip_id": trip_id})


def pay_order(client: HttpClient, auth: AuthSession, order: OrderRecord) -> ActionResult:
    response = client.request(
        "POST",
        "/api/v1/inside_pay_service/inside_payment",
        headers=auth.headers(),
        json_data={"orderId": order.order_id, "tripId": order.trip_id},
    )
    ok = response.status_code == 200
    return ActionResult(ok=ok, name="payOrder", detail=response.text, payload={"order_id": order.order_id, "trip_id": order.trip_id})


def cancel_order(client: HttpClient, auth: AuthSession, order: OrderRecord) -> ActionResult:
    response = client.request(
        "GET",
        f"/api/v1/cancelservice/cancel/{order.order_id}/{auth.user_id}",
        headers=auth.headers(),
    )
    ok = response.status_code == 200
    return ActionResult(ok=ok, name="cancelOrder", detail=response.text, payload={"order_id": order.order_id})


def collect_ticket(client: HttpClient, auth: AuthSession, order: OrderRecord) -> ActionResult:
    response = client.request(
        "GET",
        f"/api/v1/executeservice/execute/collected/{order.order_id}",
        headers=auth.headers(),
    )
    ok = response.status_code == 200
    return ActionResult(ok=ok, name="collectTicket", detail=response.text, payload={"order_id": order.order_id})


def enter_station(client: HttpClient, auth: AuthSession, order: OrderRecord) -> ActionResult:
    response = client.request(
        "GET",
        f"/api/v1/executeservice/execute/execute/{order.order_id}",
        headers=auth.headers(),
    )
    ok = response.status_code == 200
    return ActionResult(ok=ok, name="enterStation", detail=response.text, payload={"order_id": order.order_id})


def consign_order(client: HttpClient, auth: AuthSession, order: OrderRecord) -> ActionResult:
    response = client.request(
        "PUT",
        "/api/v1/consignservice/consigns",
        headers=auth.headers(),
        json_data={
            "accountId": order.account_id,
            "handleDate": time.strftime("%Y-%m-%d", time.localtime()),
            "targetDate": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "from": order.from_station,
            "to": order.to_station,
            "orderId": order.order_id,
            "consignee": "consignee",
            "phone": "12345677654",
            "weight": "32",
            "id": "",
            "isWithin": False,
        },
    )
    ok = response.status_code in (200, 201)
    return ActionResult(ok=ok, name="consignOrder", detail=response.text, payload={"order_id": order.order_id})


def rebook_order(
    client: HttpClient,
    auth: AuthSession,
    *,
    order: OrderRecord,
    new_trip_id: str,
    date: str,
    seat_type: str,
) -> ActionResult:
    response = client.request(
        "POST",
        "/api/v1/rebookservice/rebook",
        headers=auth.headers(),
        json_data={
            "oldTripId": order.trip_id,
            "orderId": order.order_id,
            "tripId": new_trip_id,
            "date": date,
            "seatType": seat_type,
        },
    )
    body = response.body or {}
    ok = response.status_code == 200 and body.get("status") == 1
    return ActionResult(ok=ok, name="rebookOrder", detail=response.text, payload={"order_id": order.order_id, "new_trip_id": new_trip_id})
