from atomic_queries import _query_advanced_ticket, build_user_headers, get_iterations, get_env_value

import logging
import time

logger = logging.getLogger("query_advanced_ticket")
date = time.strftime("%Y-%m-%d", time.localtime())


def resolve_advanced_query():
    return {
        "type": get_env_value("TT_ADVANCED_TYPE", "cheapest"),
        "date": get_env_value("TT_TRAVEL_DATE", date),
        "start": get_env_value("TT_ADVANCED_START", "Nan Jing"),
        "end": get_env_value("TT_ADVANCED_END", "Shang Hai"),
    }

if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    for i in range(iterations):
        query = resolve_advanced_query()
        place_pair = (query["start"], query["end"])
        query_type = query["type"]
        print(f"search {query_type} between {place_pair[0]} to {place_pair[1]} on {query['date']}")
        try:
            trip_ids = _query_advanced_ticket(
                place_pair=place_pair,
                headers=headers,
                time=query["date"],
                type=query_type,
            )
            print(f"get {0 if trip_ids is None else len(trip_ids)} routes.")
            print(f"trip_ids: {trip_ids}")
            print("*****************************INDEX:" + str(i))
        except Exception as e:
            print(e)

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print(f"start:{start_time} end:{end_time}")