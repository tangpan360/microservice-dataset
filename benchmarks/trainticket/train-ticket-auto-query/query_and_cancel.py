from atomic_queries import _cancel_one_order, build_user_headers, get_current_uuid, get_iterations, load_order_pairs
from bootstrap_orders import bootstrap_order
from utils import random_form_list

import time

def query_one_and_cancel(headers, uuid="4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f"):
    """
    查询order并取消order
    :param uuid:
    :param headers:
    :return:
    """
    pairs = load_order_pairs(headers=headers, types=tuple([0, 1]))
    if not pairs:
        bootstrap = bootstrap_order(headers=headers, required_status="unpaid")
        if not bootstrap:
            print("no eligible orders to cancel")
            return False
        pairs = [(bootstrap["orderId"], bootstrap["tripId"])]

    # (orderId, tripId) pair
    pair = random_form_list(pairs)

    order_id = _cancel_one_order(order_id=pair[0], uuid=uuid, headers=headers)
    if not order_id:
        return False

    print(f"{order_id} queried and canceled")
    return True


if __name__ == '__main__':
    headers = build_user_headers()
    uuid = get_current_uuid()
    iterations = get_iterations()
    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    all_ok = True

    for i in range(iterations):
        all_ok = query_one_and_cancel(headers=headers, uuid=uuid) and all_ok
        print("*****************************INDEX:" + str(i))

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time} end:{end_time}")
    if not all_ok:
        raise SystemExit(1)
