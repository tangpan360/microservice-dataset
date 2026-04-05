from query_and_preserve import query_and_preserve
from query_order_and_pay import query_order_and_pay
from query_and_collect_ticket import query_and_collect_ticket
from query_and_enter_station import query_and_enter_station
from query_and_cancel import query_one_and_cancel

import os
import random
import time
from threading import Thread

from atomic_queries import (
    _login,
    _query_high_speed_ticket,
    build_user_headers,
    get_env_float,
    get_iterations,
    load_order_pairs,
)


def resolve_manager_flow() -> str:
    flow = os.environ.get("TT_MANAGER_FLOW", "mixed").lower()
    if flow in ("cancel", "pay_collect_enter", "mixed"):
        return flow
    return "mixed"


THREAD_ERRORS = []


def main():
    headers = build_user_headers()
    iterations = get_iterations(1)
    flow = resolve_manager_flow()
    cancel_probability = min(1.0, max(0.0, get_env_float("TT_CANCEL_PROBABILITY", 0.25)))

    for i in range(iterations):
        now_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"now_time:{now_time}")

        if i % 20 == 0:
            uid, token = _login()
            if uid is not None and token is not None:
                headers['Authorization'] = "Bearer " + token

        print(f"idx:{i}")
        preserved = query_and_preserve(headers)
        if not preserved:
            print("skip downstream order flow because preserve did not succeed")
            continue

        if flow == "cancel":
            query_one_and_cancel(headers)
            continue

        if flow == "mixed" and random.random() < cancel_probability:
            query_one_and_cancel(headers)
        else:
            paid = query_order_and_pay(headers)
            if not paid:
                print("skip collect and enter because pay did not succeed")
                continue

            collected = query_and_collect_ticket(headers)
            if not collected:
                print("skip enter because collect did not succeed")
                continue

            query_and_enter_station(headers)


def run_main_with_error_capture():
    try:
        main()
    except Exception as exc:
        THREAD_ERRORS.append(exc)
        raise


def main_thread():
    threads = []
    thread_count = max(1, int(os.environ.get("TT_THREADS", "1")))

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time}")

    for i in range(thread_count):
        t = Thread(name="thread" + str(i), target=run_main_with_error_capture)
        time.sleep(1)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time} end:{end_time}")
    if THREAD_ERRORS:
        raise RuntimeError(f"normal_request_manager encountered {len(THREAD_ERRORS)} thread error(s)")


def query_order():
    headers = build_user_headers()
    uid, token = _login()
    if uid is not None and token is not None:
        headers['Authorization'] = "Bearer " + token

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time}")

    for i in range(get_iterations(1)):
        pairs = load_order_pairs(headers=headers, types=tuple([0, 1]), env_name="TT_ORDER_SOURCE", default="high_speed")
        print(pairs)

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time} end:{end_time}")


def query_tickets():
    headers = build_user_headers()
    uid, token = _login()
    if uid is not None and token is not None:
        headers['Authorization'] = "Bearer " + token


    date = time.strftime("%Y-%m-%d", time.localtime())

    start = "Shang Hai"
    end = "Su Zhou"
    high_speed_place_pair = (start, end)

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time}")

    for i in range(get_iterations(1)):
        trip_ids = _query_high_speed_ticket(place_pair=high_speed_place_pair, headers=headers, time=date)
        print(trip_ids)

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time} end:{end_time}")


if __name__ == '__main__':
    main_thread()

