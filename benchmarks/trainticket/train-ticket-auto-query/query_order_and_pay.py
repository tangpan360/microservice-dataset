import time

from bootstrap_orders import bootstrap_order
from atomic_queries import _pay_one_order, build_user_headers, get_iterations, load_order_pairs
from utils import random_form_list


def query_order_and_pay(headers, pairs=None):
    """
    查询Order并付款未付款Order
    :return:
    """
    if pairs is None:
        pairs = load_order_pairs(headers=headers, types=tuple([0, 1]))
    # (orderId, tripId) pair
    if not pairs:
        bootstrap = bootstrap_order(headers=headers, required_status="unpaid")
        if not bootstrap:
            print("no eligible orders to pay")
            return False
        pairs = [(bootstrap["orderId"], bootstrap["tripId"])]
    pair = random_form_list(pairs)

    order_id = _pay_one_order(pair[0], pair[1], headers=headers)
    if not order_id:
        return False

    print(f"{order_id} queried and paid")
    return True


if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()
    all_ok = True

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    for i in range(iterations):
        try:
            pairs = load_order_pairs(headers=headers, types=tuple([0, 1]))
            all_ok = query_order_and_pay(headers=headers, pairs=pairs) and all_ok
            print("*****************************INDEX:" + str(i))
        except Exception as e:
            print(e)
            all_ok = False

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print(f"start:{start_time} end:{end_time}")
    if not all_ok:
        raise SystemExit(1)
