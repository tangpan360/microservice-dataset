import time

from atomic_queries import _query_route, build_user_headers, get_env_value, get_iterations

def query_route(headers):
    route_id = get_env_value("TT_ROUTE_ID", "92708982-77af-4318-be25-57ccb0ff69ad")
    _query_route(routeId=route_id, headers=headers)
    print(f"route_id: {route_id}")


if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()
    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    for i in range(iterations):
        query_route(headers=headers)
        print("*****************************INDEX:" + str(i))

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time} end:{end_time}")
