try:
    from .queries import Query
    from .utils import *
except ImportError:
    from queries import Query
    from utils import *
import logging
import os

logger = logging.getLogger("autoquery-scenario")
highspeed_weights = {True: 60, False: 40}


def get_env_value(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def resolve_query_other() -> bool:
    mode = get_env_value("TT_ORDER_SOURCE", "auto").lower()
    if mode == "high_speed":
        return False
    if mode == "normal":
        return True
    return not random_from_weighted(highspeed_weights)


def resolve_preserve_context():
    mode = get_env_value("TT_PRESERVE_MODE", "auto").lower()
    if mode == "high_speed":
        high_speed = True
    elif mode == "normal":
        high_speed = False
    else:
        high_speed = random_from_weighted(highspeed_weights)

    start = get_env_value("TT_PRESERVE_START", "Shang Hai")
    default_end = "Su Zhou" if high_speed else "Nan Jing"
    end = get_env_value("TT_PRESERVE_END", default_end)
    return high_speed, start, end


def query_and_cancel(q: Query):
    pairs = q.query_orders(types=tuple([0, 1]), query_other=resolve_query_other())

    if not pairs:
        return False

    # (orderId, tripId)
    pair = random_from_list(pairs)

    order_id = q.cancel_order(order_id=pair[0])
    if not order_id:
        return False

    logger.info(f"{order_id} queried and canceled")
    return True


def query_and_collect(q: Query):
    pairs = q.query_orders(types=tuple([1]), query_other=resolve_query_other())

    if not pairs:
        return False

    # (orderId, tripId)
    pair = random_from_list(pairs)

    order_id = q.collect_order(order_id=pair[0])
    if not order_id:
        return False

    logger.info(f"{order_id} queried and collected")
    return True


def query_and_execute(q: Query):
    pairs = q.query_orders(types=tuple([1]), query_other=resolve_query_other())

    if not pairs:
        return False

    # (orderId, tripId)
    pair = random_from_list(pairs)

    order_id = q.enter_station(order_id=pair[0])
    if not order_id:
        return False

    logger.info(f"{order_id} queried and entered station")
    return True


def query_and_preserve(q: Query):
    high_speed, start, end = resolve_preserve_context()
    if high_speed:
        high_speed_place_pair = (start, end)
        trip_ids = q.query_high_speed_ticket(place_pair=high_speed_place_pair)
    else:
        other_place_pair = (start, end)
        trip_ids = q.query_normal_ticket(place_pair=other_place_pair)

    _ = q.query_assurances()

    return q.preserve(start, end, trip_ids, high_speed, date=get_env_value("TT_TRAVEL_DATE", ""))


def query_and_consign(q: Query):
    records = q.query_orders_all_info(query_other=resolve_query_other())

    if not records:
        return False

    # (orderId, tripId)
    res = random_from_list(records)
    order_id = q.put_consign(res)

    if not order_id:
        return False

    logger.info(f"{order_id} queried and put consign")
    return True


def query_and_pay(q: Query):
    pairs = q.query_orders(types=tuple([0, 1]), query_other=resolve_query_other())

    if not pairs:
        return False

    # (orderId, tripId)
    pair = random_from_list(pairs)
    order_id = q.pay_order(pair[0], pair[1])

    if not order_id:
        return False

    logger.info(f"{order_id} queried and paid")
    return True


def query_and_rebook(q: Query):
    pairs = q.query_orders(types=tuple([1]), query_other=resolve_query_other())

    if not pairs:
        return False

    # (orderId, tripId)
    pair = random_from_list(pairs)
    new_trip_id = get_env_value("TT_REBOOK_NEW_TRIP_ID", pair[1])
    new_date = get_env_value("TT_TRAVEL_DATE", "")
    new_seat_type = get_env_value("TT_REBOOK_SEAT_TYPE", "")

    order_id = q.rebook_ticket(pair[0], pair[1], new_trip_id, new_date, new_seat_type)
    if not order_id:
        return False

    logger.info(f"{order_id} queried and rebooked")
    return True