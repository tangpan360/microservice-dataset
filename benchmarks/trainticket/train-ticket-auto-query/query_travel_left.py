from atomic_queries import _query_high_speed_ticket, _query_normal_ticket, build_user_headers, get_iterations, get_env_value
from utils import random_boolean

import logging
import os
import time

logger = logging.getLogger("query_travel_left")
date = time.strftime("%Y-%m-%d", time.localtime())


def resolve_query_mode() -> str:
    mode = os.environ.get("TT_QUERY_MODE", "auto").strip().lower()
    if mode in {"high_speed", "normal"}:
        return mode
    return "auto"


def resolve_place_pair(high_speed: bool):
    if high_speed:
        default_start, default_end = "Shang Hai", "Su Zhou"
    else:
        default_start, default_end = "Shang Hai", "Nan Jing"
    return (
        get_env_value("TT_TRAVEL_START", default_start),
        get_env_value("TT_TRAVEL_END", default_end),
    )


def query_travel_left(headers):
    """
    1. 查票（随机高铁或普通）
    2. 查保险、Food、Contacts
    3. 随机选择Contacts、保险、是否买食物、是否托运
    4. 买票
    :return:
    """
    mode = resolve_query_mode()
    high_speed = random_boolean() if mode == "auto" else mode == "high_speed"
    query_date = get_env_value("TT_TRAVEL_DATE", date)
    place_pair = resolve_place_pair(high_speed)
    if high_speed:
        trip_ids = _query_high_speed_ticket(place_pair=place_pair, headers=headers, time=query_date)
    else:
        trip_ids = _query_normal_ticket(place_pair=place_pair, headers=headers, time=query_date)

    query_type = "high_speed" if high_speed else "normal"
    print(f"query_type: {query_type}, place_pair: {place_pair}, date: {query_date}, trip_ids: {trip_ids}")
    return trip_ids


if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time}")

    for i in range(iterations):
        try:
            query_travel_left(headers=headers)
            print("*****************************INDEX:" + str(i))
        except Exception as e:
            print(e)
    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print(f"start:{start_time} end:{end_time}")
