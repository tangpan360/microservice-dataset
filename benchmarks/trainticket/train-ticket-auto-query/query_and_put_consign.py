import time

from bootstrap_orders import bootstrap_order
from atomic_queries import _put_consign, build_user_headers, get_iterations, load_order_info_records
from utils import random_form_list


def query_one_and_put_consign(headers, pairs=None):
    """
    查询order并put consign
    :param uuid:
    :param headers:
    :return:
    """
    if pairs is None:
        pairs = load_order_info_records(headers=headers)
    if not pairs:
        bootstrap = bootstrap_order(headers=headers, required_status="unpaid")
        if not bootstrap:
            print("no eligible orders to consign")
            return False
        pairs = [{
            "accountId": bootstrap["accountId"],
            "targetDate": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
            "orderId": bootstrap["orderId"],
            "from": bootstrap["from"],
            "to": bootstrap["to"],
        }]
    pair = random_form_list(pairs)

    order_id = _put_consign(result=pair, headers=headers)
    if not order_id:
        return False

    print(f"{order_id} queried and put consign")
    return True


if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()
    all_ok = True

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    for i in range(iterations):
        try:
            pairs = load_order_info_records(headers=headers)
            all_ok = query_one_and_put_consign(headers=headers, pairs=pairs) and all_ok
            print("*****************************INDEX:" + str(i))
        except Exception as e:
            print(e)
            all_ok = False

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print(f"start:{start_time} end:{end_time}")
    if not all_ok:
        raise SystemExit(1)
