from atomic_queries import _query_high_speed_ticket, _query_normal_ticket, _query_assurances, _query_food, _query_contacts, build_user_headers, get_iterations, base_address, get_current_uuid, REQUEST_TIMEOUT, get_env_value, _request_with_retry, _response_json
from utils import random_boolean, random_phone, random_str, random_form_list

import logging
import random
import requests
import time

logger = logging.getLogger("query_and_preserve")
date = time.strftime("%Y-%m-%d", time.localtime())


def resolve_toggle(name: str) -> bool:
    value = get_env_value(name, "auto").lower()
    if value in ("1", "true", "yes", "y", "on"):
        return True
    if value in ("0", "false", "no", "n", "off"):
        return False
    return random_boolean()


def resolve_preserve_query():
    mode = get_env_value("TT_PRESERVE_MODE", "auto").lower()
    if mode not in ("auto", "high_speed", "normal"):
        mode = "auto"

    if mode == "high_speed":
        high_speed = True
    elif mode == "normal":
        high_speed = False
    else:
        high_speed = random_boolean()

    default_start = "Shang Hai"
    default_end = "Su Zhou" if high_speed else "Nan Jing"
    return {
        "high_speed": high_speed,
        "date": get_env_value("TT_TRAVEL_DATE", date),
        "start": get_env_value("TT_PRESERVE_START", default_start),
        "end": get_env_value("TT_PRESERVE_END", default_end),
        "need_food": resolve_toggle("TT_PRESERVE_NEED_FOOD"),
        "need_assurance": resolve_toggle("TT_PRESERVE_NEED_ASSURANCE"),
        "need_consign": resolve_toggle("TT_PRESERVE_NEED_CONSIGN"),
    }


def query_and_preserve(headers):
    """
    1. 查票（随机高铁或普通）
    2. 查保险、Food、Contacts
    3. 随机选择Contacts、保险、是否买食物、是否托运
    4. 买票
    :return:
    """
    query = resolve_preserve_query()
    start = query["start"]
    end = query["end"]
    query_date = query["date"]
    trip_ids = []
    PRESERVE_URL = ""

    high_speed = query["high_speed"]
    if high_speed:
        high_speed_place_pair = (start, end)
        trip_ids = _query_high_speed_ticket(place_pair=high_speed_place_pair, headers=headers, time=query_date)
        PRESERVE_URL = f"{base_address}/api/v1/preserveservice/preserve"
    else:
        other_place_pair = (start, end)
        trip_ids = _query_normal_ticket(place_pair=other_place_pair, headers=headers, time=query_date)
        PRESERVE_URL = f"{base_address}/api/v1/preserveotherservice/preserveOther"

    _ = _query_assurances(headers=headers)
    food_result = _query_food(headers=headers)
    contacts_result = _query_contacts(headers=headers)
    if not trip_ids:
        print("no trips returned for preserve")
        return False
    if not contacts_result:
        print("no contacts returned for preserve")
        return False

    base_preserve_payload = {
        "accountId": get_current_uuid(),
        "assurance": "0",
        "contactsId": "",
        "date": query_date,
        "from": start,
        "to": end,
        "tripId": ""
    }

    trip_id = random_form_list(trip_ids)
    base_preserve_payload["tripId"] = trip_id

    need_food = query["need_food"]
    if need_food:
        logger.info("need food")
        if not food_result:
            print("food requested but no food options returned")
            return False
        food_dict = random_form_list(food_result)
        base_preserve_payload.update(food_dict)
    else:
        logger.info("not need food")
        base_preserve_payload["foodType"] = "0"

    need_assurance = query["need_assurance"]
    if need_assurance:
        base_preserve_payload["assurance"] = 1

    contacts_id = random_form_list(contacts_result)
    base_preserve_payload["contactsId"] = contacts_id

    # 高铁 2-3
    seat_type = random_form_list(["2", "3"])
    base_preserve_payload["seatType"] = seat_type

    need_consign = query["need_consign"]
    if need_consign:
        consign = {
            "consigneeName": random_str(),
            "consigneePhone": random_phone(),
            "consigneeWeight": random.randint(1, 10),
            "handleDate": query_date
        }
        base_preserve_payload.update(consign)

    print("payload:" + str(base_preserve_payload))

    print(f"choices: preserve_high: {high_speed} need_food:{need_food}  need_consign: {need_consign}  need_assurance:{need_assurance}")

    res = _request_with_retry(
        "POST",
        PRESERVE_URL,
        headers=headers,
        json=base_preserve_payload,
        timeout=REQUEST_TIMEOUT,
    )
    body = _response_json(res)
    print(body)
    if res is None or res.status_code != 200 or body is None or body.get("data") != "Success":
        print("preserve failed")
        return False
    return True


if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    for i in range(iterations):
        try:
            query_and_preserve(headers=headers)
            print("*****************************INDEX:" + str(i))
        except Exception as e:
            print(e)

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print(f"start:{start_time} end:{end_time}")
