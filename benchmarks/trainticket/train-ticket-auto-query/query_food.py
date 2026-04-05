from atomic_queries import _query_food, build_user_headers, get_iterations, get_env_value

import logging
import time

logger = logging.getLogger("query_food")
date = time.strftime("%Y-%m-%d", time.localtime())

def resolve_food_query():
    return {
        "date": get_env_value("TT_TRAVEL_DATE", date),
        "start": get_env_value("TT_FOOD_START", "Shang Hai"),
        "end": get_env_value("TT_FOOD_END", "Su Zhou"),
        "trip_id": get_env_value("TT_FOOD_TRIP_ID", "D1345"),
    }


def query_food(headers):
    query = resolve_food_query()
    food = _query_food(
        place_pair=(query["start"], query["end"]),
        train_num=query["trip_id"],
        headers=headers,
        date=query["date"],
    )
    print(f"food_query: {query}")
    print(f"food_result: {food}")
    return food


if __name__ == '__main__':
    headers = build_user_headers()
    iterations = get_iterations()

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    for i in range(iterations):
        try:
            query_food(headers=headers)
            print("*****************************INDEX:" + str(i))
        except Exception as e:
            print(e)

    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print(f"start:{start_time} end:{end_time}")
