from atomic_queries import _query_high_speed_ticket_parallel, build_user_headers, get_iterations, get_env_value

import logging
import time

logger = logging.getLogger("query_travel_left_parallel")
date = time.strftime("%Y-%m-%d", time.localtime())

def resolve_parallel_query():
    return {
        "date": get_env_value("TT_TRAVEL_DATE", date),
        "start": get_env_value("TT_PARALLEL_START", "Su Zhou"),
        "end": get_env_value("TT_PARALLEL_END", "Shang Hai"),
    }


def query_travel_left_parallel(headers):
    query = resolve_parallel_query()
    place_pair = (query["start"], query["end"])
    trip_ids = _query_high_speed_ticket_parallel(place_pair=place_pair, headers=headers, time=query["date"])
    print(f"parallel_query: {query}, trip_ids: {trip_ids}")
    return trip_ids


if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"start:{start_time}")

    for i in range(iterations):
        try:
            query_travel_left_parallel(headers=headers)
            print("*****************************INDEX:" + str(i))
        except Exception as e:
            print(e)
    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print(f"start:{start_time} end:{end_time}")
