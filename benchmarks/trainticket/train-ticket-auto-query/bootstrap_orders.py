import time
from typing import Optional

from atomic_queries import (
    REQUEST_TIMEOUT,
    _collect_one_order,
    _pay_one_order,
    _query_contacts,
    _query_high_speed_ticket,
    _query_normal_ticket,
    _request_with_retry,
    _response_json,
    base_address,
    get_current_uuid,
    get_env_value,
)
from utils import random_form_list


def resolve_bootstrap_context():
    source = get_env_value("TT_BOOTSTRAP_ORDER_SOURCE", "normal").lower()
    use_other_order = source != "high_speed"
    query_date = get_env_value("TT_BOOTSTRAP_DATE", time.strftime("%Y-%m-%d", time.localtime()))

    if use_other_order:
        return {
            "query_other": True,
            "date": query_date,
            "start": get_env_value("TT_BOOTSTRAP_START", "Shang Hai"),
            "end": get_env_value("TT_BOOTSTRAP_END", "Nan Jing"),
            "seat_type": get_env_value("TT_BOOTSTRAP_SEAT_TYPE", "3"),
            "preserve_url": f"{base_address}/api/v1/preserveotherservice/preserveOther",
            "refresh_url": f"{base_address}/api/v1/orderOtherService/orderOther/refresh",
            "query_fn": _query_normal_ticket,
        }

    return {
        "query_other": False,
        "date": query_date,
        "start": get_env_value("TT_BOOTSTRAP_START", "Shang Hai"),
        "end": get_env_value("TT_BOOTSTRAP_END", "Su Zhou"),
        "seat_type": get_env_value("TT_BOOTSTRAP_SEAT_TYPE", "2"),
        "preserve_url": f"{base_address}/api/v1/preserveservice/preserve",
        "refresh_url": f"{base_address}/api/v1/orderservice/order/refresh",
        "query_fn": _query_high_speed_ticket,
    }


def _query_orders_raw(headers, refresh_url: str):
    payload = {"loginId": get_current_uuid()}
    response = _request_with_retry("POST", refresh_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    body = _response_json(response)
    if response is None or response.status_code != 200 or body is None or body.get("data") is None:
        return []
    return body.get("data") or []


def _same_travel_day(order: dict, query_date: str) -> bool:
    travel_date = order.get("travelDate")
    if travel_date is None:
        return False
    try:
        travel_day = time.strftime("%Y-%m-%d", time.localtime(travel_date / 1000))
    except (TypeError, ValueError, OSError):
        return False
    return travel_day == query_date


def _find_latest_order(orders, query_date: str, trip_id: str, allowed_statuses):
    candidates = []
    for item in orders:
        if item.get("trainNumber") != trip_id:
            continue
        if item.get("status") not in allowed_statuses:
            continue
        if not _same_travel_day(item, query_date):
            continue
        candidates.append(item)

    if not candidates:
        return None

    candidates.sort(key=lambda item: item.get("boughtDate") or 0, reverse=True)
    return candidates[0]


def bootstrap_order(headers, required_status: str = "unpaid") -> Optional[dict]:
    context = resolve_bootstrap_context()
    trip_ids = context["query_fn"](
        place_pair=(context["start"], context["end"]),
        headers=headers,
        time=context["date"],
    ) or []
    if not trip_ids:
        print(
            f"bootstrap order failed: no trip ids for "
            f"{context['start']} -> {context['end']} on {context['date']}"
        )
        return None

    trip_id = get_env_value("TT_BOOTSTRAP_TRIP_ID", trip_ids[0])
    if trip_id not in trip_ids:
        trip_id = trip_ids[0]

    contacts = _query_contacts(headers=headers) or []
    if not contacts:
        print("bootstrap order failed: no contacts")
        return None

    preserve_payload = {
        "accountId": get_current_uuid(),
        "assurance": "0",
        "contactsId": random_form_list(contacts),
        "date": context["date"],
        "from": context["start"],
        "to": context["end"],
        "tripId": trip_id,
        "foodType": "0",
        "seatType": context["seat_type"],
    }
    response = _request_with_retry(
        "POST",
        context["preserve_url"],
        headers=headers,
        json=preserve_payload,
        timeout=REQUEST_TIMEOUT,
    )
    body = _response_json(response)
    if response is None or response.status_code != 200 or body is None or body.get("status") != 1:
        print(
            "bootstrap order preserve failed: "
            f"{body if body is not None else (response.text if response is not None else 'no response')}"
        )
        return None

    order = None
    for _ in range(5):
        orders = _query_orders_raw(headers=headers, refresh_url=context["refresh_url"])
        order = _find_latest_order(orders, context["date"], trip_id, {0, 1, 2, 3, 4, 5, 6})
        if order is not None:
            break
        time.sleep(1)

    if order is None:
        print(f"bootstrap order failed: could not locate order for {trip_id} on {context['date']}")
        return None

    order_id = order.get("id")
    status = order.get("status")

    if required_status in ("paid", "collected") and status == 0:
        paid_order_id = _pay_one_order(order_id, trip_id, headers=headers)
        if not paid_order_id:
            return None
        order_id = paid_order_id
        status = 1

    if required_status == "collected" and status == 1:
        collected_order_id = _collect_one_order(order_id, headers=headers)
        if not collected_order_id:
            return None
        order_id = collected_order_id
        status = 2

    return {
        "orderId": order_id,
        "tripId": trip_id,
        "status": status,
        "accountId": order.get("accountId"),
        "from": order.get("from"),
        "to": order.get("to"),
        "query_other": context["query_other"],
        "date": context["date"],
    }
