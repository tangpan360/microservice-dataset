import logging
import time

from atomic_queries import _query_admin_basic_price, build_admin_headers, get_iterations

logger = logging.getLogger("query_admin_basic_price")

def query_admin_basic_price(headers):
    _query_admin_basic_price(headers=headers)


if __name__ == '__main__':
    headers = build_admin_headers()
    iterations = get_iterations()

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    for i in range(iterations):
        try:
            query_admin_basic_price(headers=headers)
            print("*****************************INDEX:" + str(i))
        except Exception as e:
            print(e)
    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print(f"start:{start_time} end:{end_time}")
