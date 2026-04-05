import time

from bootstrap_orders import bootstrap_order
from atomic_queries import _collect_one_order, build_user_headers, get_iterations, load_order_pairs
from utils import random_form_list


def query_and_collect_ticket(headers):

    pairs = load_order_pairs(headers=headers, types=tuple([1]))
    if not pairs:
        bootstrap = bootstrap_order(headers=headers, required_status="paid")
        if not bootstrap:
            print("no eligible orders to collect")
            return False
        pairs = [(bootstrap["orderId"], bootstrap["tripId"])]

    # (orderId, tripId)
    pair = random_form_list(pairs)

    order_id = _collect_one_order(order_id=pair[0], headers=headers)
    if not order_id:
        return False

    print(f"{order_id} queried and collected")
    return True


if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()
    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    all_ok = True

    for i in range(iterations):
        all_ok = query_and_collect_ticket(headers=headers) and all_ok
        print("*****************************INDEX:" + str(i))

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time} end:{end_time}")
    if not all_ok:
        raise SystemExit(1)
