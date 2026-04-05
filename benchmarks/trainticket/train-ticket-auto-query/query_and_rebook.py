import time
from typing import Optional

from atomic_queries import (
    REQUEST_TIMEOUT,
    _pay_one_order,
    _query_contacts,
    _query_high_speed_ticket,
    _rebook_ticket,
    _request_with_retry,
    _response_json,
    base_address,
    build_user_headers,
    get_current_uuid,
    get_env_value,
    get_iterations,
)
from utils import random_form_list


def resolve_rebook_context():
    tomorrow = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400))
    return {
        "date": get_env_value("TT_REBOOK_DATE", tomorrow),
        "start": get_env_value("TT_REBOOK_START", "Nan Jing"),
        "end": get_env_value("TT_REBOOK_END", "Shang Hai"),
        "seat_type": get_env_value("TT_REBOOK_SEAT_TYPE", "2"),
    }


def _query_latest_high_speed_order(headers, query_date: str, trip_id: str) -> Optional[dict]:
    url = f"{base_address}/api/v1/orderservice/order/refresh"
    payload = {"loginId": get_current_uuid()}

    for _ in range(5):
        response = _request_with_retry("POST", url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        body = _response_json(response)
        data = body.get("data") if body is not None else None
        if response is not None and response.status_code == 200 and data is not None:
            candidates = []
            for item in data:
                travel_date = item.get("travelDate")
                if travel_date is None:
                    continue
                travel_day = time.strftime("%Y-%m-%d", time.localtime(travel_date / 1000))
                if travel_day != query_date:
                    continue
                if item.get("trainNumber") != trip_id:
                    continue
                if item.get("status") not in (0, 1):
                    continue
                candidates.append(item)

            if candidates:
                candidates.sort(key=lambda item: item.get("boughtDate") or 0, reverse=True)
                return candidates[0]

        time.sleep(1)

    return None


def _create_paid_rebook_order(headers, query_date: str, start: str, end: str, seat_type: str):
    trip_ids = _query_high_speed_ticket(place_pair=(start, end), headers=headers, time=query_date) or []
    if len(trip_ids) < 2:
        print(f"not enough trip choices to rebook between {start} and {end} on {query_date}: {trip_ids}")
        return None, None, None

    old_trip_id = get_env_value("TT_REBOOK_OLD_TRIP_ID", trip_ids[0])
    if old_trip_id not in trip_ids:
        print(f"configured old trip id {old_trip_id} is not available: {trip_ids}")
        return None, None, None

    available_new_trip_ids = [trip_id for trip_id in trip_ids if trip_id != old_trip_id]
    if not available_new_trip_ids:
        print(f"no alternative trip ids available for rebook: {trip_ids}")
        return None, None, None

    requested_new_trip_id = get_env_value("TT_REBOOK_NEW_TRIP_ID", available_new_trip_ids[0])
    new_trip_id = requested_new_trip_id if requested_new_trip_id in available_new_trip_ids else available_new_trip_ids[0]

    contact_ids = _query_contacts(headers=headers) or []
    if not contact_ids:
        print("no contacts returned for rebook bootstrap")
        return None, None, None

    payload = {
        "accountId": get_current_uuid(),
        "assurance": "0",
        "contactsId": random_form_list(contact_ids),
        "date": query_date,
        "from": start,
        "to": end,
        "tripId": old_trip_id,
        "foodType": "0",
        "seatType": seat_type,
    }
    preserve_url = f"{base_address}/api/v1/preserveservice/preserve"
    response = _request_with_retry("POST", preserve_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    body = _response_json(response)
    if response is None or response.status_code != 200 or body is None or body.get("status") != 1:
        print(f"rebook bootstrap preserve failed: {body if body is not None else (response.text if response is not None else 'no response')}")
        return None, None, None

    order = _query_latest_high_speed_order(headers=headers, query_date=query_date, trip_id=old_trip_id)
    if order is None:
        print(f"could not locate freshly preserved order for trip {old_trip_id} on {query_date}")
        return None, None, None

    order_id = order.get("id")
    if order.get("status") == 0:
        paid_order_id = _pay_one_order(order_id, old_trip_id, headers=headers)
        if not paid_order_id:
            return None, None, None
        order_id = paid_order_id

    return order_id, old_trip_id, new_trip_id


def query_and_rebook(headers):
    context = resolve_rebook_context()
    order_id, old_trip_id, new_trip_id = _create_paid_rebook_order(
        headers=headers,
        query_date=context["date"],
        start=context["start"],
        end=context["end"],
        seat_type=context["seat_type"],
    )
    if not order_id or not old_trip_id or not new_trip_id:
        return False

    rebooked_order_id = _rebook_ticket(
        old_order_id=order_id,
        old_trip_id=old_trip_id,
        new_trip_id=new_trip_id,
        new_date=context["date"],
        new_seat_type=context["seat_type"],
        headers=headers,
    )
    if not rebooked_order_id:
        return False

    print(f"{rebooked_order_id} queried and rebooked to {new_trip_id}")
    return True





if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()
    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    all_ok = True

    for i in range(iterations):
        all_ok = query_and_rebook(headers=headers) and all_ok
        print("*****************************INDEX:" + str(i))

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print(f"start:{start_time} end:{end_time}")
    if not all_ok:
        raise SystemExit(1)