import time

from bootstrap_orders import bootstrap_order
from atomic_queries import _enter_station, build_user_headers, get_iterations, load_order_pairs
from utils import random_form_list


def query_and_enter_station(headers):
    pairs = load_order_pairs(headers=headers, types=tuple([2]))
    if not pairs:
        bootstrap = bootstrap_order(headers=headers, required_status="collected")
        if not bootstrap:
            print("no eligible orders to enter station")
            return False
        pairs = [(bootstrap["orderId"], bootstrap["tripId"])]

    # (orderId, tripId)
    pair = random_form_list(pairs)

    order_id = _enter_station(order_id=pair[0], headers=headers)
    if not order_id:
        return False

    print(f"{order_id} queried and entered station")
    return True


if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()
    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    all_ok = True

    for i in range(iterations):
        all_ok = query_and_enter_station(headers=headers) and all_ok
        print("*****************************INDEX:" + str(i))

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time} end:{end_time}")
    if not all_ok:
        raise SystemExit(1)
