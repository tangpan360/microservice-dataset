from typing import List
import logging
import os
import time

import requests

logger = logging.getLogger("atomic_queries")
base_address = os.environ.get("TT_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
REQUEST_TIMEOUT = float(os.environ.get("TT_TIMEOUT", "20"))
DEFAULT_USER = os.environ.get("TT_USERNAME", "fdse_microservice")
DEFAULT_PASSWORD = os.environ.get("TT_PASSWORD", "111111")
DEFAULT_ADMIN_USER = os.environ.get("TT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.environ.get("TT_ADMIN_PASSWORD", "222222")

headers = {
    "Content-Type": "application/json",
    "Connection": "close"
}

uuid = "4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f"

date = time.strftime("%Y-%m-%d", time.localtime())


def get_iterations(default: int = 1) -> int:
    value = os.environ.get("TT_ITERATIONS")
    if value is None:
        return default
    try:
        return max(1, int(value))
    except ValueError:
        return default


def get_env_value(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def get_env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def resolve_order_query_other_flags(env_name: str = "TT_ORDER_SOURCE", default: str = "both") -> List[bool]:
    mode = get_env_value(env_name, default).lower()
    if mode == "high_speed":
        return [False]
    if mode == "normal":
        return [True]
    return [False, True]


def load_order_pairs(headers: dict = {}, types: tuple = tuple([0]), env_name: str = "TT_ORDER_SOURCE",
                     default: str = "both") -> List[tuple]:
    pairs = []
    for query_other in resolve_order_query_other_flags(env_name=env_name, default=default):
        pairs.extend(_query_orders(headers=headers, types=types, query_other=query_other) or [])
    return pairs


def load_order_info_records(headers: dict = {}, env_name: str = "TT_ORDER_SOURCE",
                            default: str = "both") -> List[dict]:
    records = []
    for query_other in resolve_order_query_other_flags(env_name=env_name, default=default):
        records.extend(_query_orders_all_info(headers=headers, query_other=query_other) or [])
    return records


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Connection": "close",
    }


def _request_with_retry(method: str, url: str, headers: dict = None, json: dict = None,
                        timeout: float = None, retries: int = None, retry_sleep: float = None):
    timeout = REQUEST_TIMEOUT if timeout is None else timeout
    retries = max(1, int(get_env_float("TT_REQUEST_RETRIES", 3))) if retries is None else max(1, retries)
    retry_sleep = get_env_float("TT_REQUEST_RETRY_SLEEP", 1.0) if retry_sleep is None else retry_sleep

    response = None
    last_error = "unknown request failure"
    for attempt in range(retries):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                timeout=timeout,
            )
            if response.status_code < 500:
                return response
            last_error = f"status={response.status_code} body={response.text}"
        except requests.RequestException as exc:
            response = None
            last_error = str(exc)

        if attempt + 1 < retries:
            logger.warning(f"{method} {url} transient failure {attempt + 1}/{retries}: {last_error}")
            time.sleep(retry_sleep)

    if response is None:
        logger.warning(f"{method} {url} failed after {retries} attempts: {last_error}")
    return response


def _response_json(response):
    if response is None:
        return None
    try:
        return response.json()
    except ValueError:
        logger.warning(f"invalid json response from {response.url}: {response.text}")
        return None


def get_current_uuid() -> str:
    return uuid


def _login(username=DEFAULT_USER, password=DEFAULT_PASSWORD):
    global uuid
    url = f"{base_address}/api/v1/users/login"
    retries = max(1, int(get_env_float("TT_LOGIN_RETRIES", 3)))
    retry_sleep = get_env_float("TT_LOGIN_RETRY_SLEEP", 1.0)

    payload = {
        "username": username,
        "password": password,
        # The auth service only validates captcha when this value is non-empty.
        "verificationCode": "",
    }
    request_headers = {
        "Content-Type": "application/json",
        "Connection": "close",
    }

    last_error = "unknown login failure"
    for attempt in range(retries):
        try:
            r = requests.post(url=url, headers=request_headers, json=payload, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                body = r.json()
                data = body.get("data")
                if body.get("status") == 1 and data is not None:
                    uid = data.get("userId")
                    token = data.get("token")
                    if uid and token:
                        uuid = uid
                        return uid, token
                last_error = str(body)
            else:
                last_error = f"status={r.status_code}, body={r.text}"
        except requests.RequestException as exc:
            last_error = str(exc)

        if attempt + 1 < retries:
            logger.warning(f"login attempt {attempt + 1}/{retries} failed for {username}: {last_error}")
            time.sleep(retry_sleep)

    logger.warning(f"login failed for {username} after {retries} attempts: {last_error}")

    return None, None


def admin_login():
    return _login(DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASSWORD)


def build_user_headers(username=DEFAULT_USER, password=DEFAULT_PASSWORD) -> dict:
    uid, token = _login(username, password)
    if uid is None or token is None:
        raise RuntimeError(f"login failed for user '{username}' at {base_address}")
    return _auth_headers(token)


def build_admin_headers(username=DEFAULT_ADMIN_USER, password=DEFAULT_ADMIN_PASSWORD) -> dict:
    uid, token = _login(username, password)
    if uid is None or token is None:
        raise RuntimeError(f"login failed for admin user '{username}' at {base_address}")
    return _auth_headers(token)


def _query_high_speed_ticket(place_pair: tuple = ("Shang Hai", "Su Zhou"), headers: dict = {},
                             time: str = "2021-07-15") -> List[str]:
    """
    返回TripId 列表
    :param place_pair: 使用的开始结束组对
    :param headers: 请求头
    :return: TripId 列表
    """

    url = f"{base_address}/api/v1/travelservice/trips/left"
    place_pairs = [("Shang Hai", "Su Zhou"),
                   ("Su Zhou", "Shang Hai"),
                   ("Nan Jing", "Shang Hai")]

    payload = {
        "departureTime": time,
        "startingPlace": place_pair[0],
        "endPlace": place_pair[1],
    }

    response = _request_with_retry("POST", url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    body = _response_json(response)

    if response is None or response.status_code != 200 or body is None or body.get("data") is None:
        logger.warning(f"request for {url} failed. response data is {response.text if response is not None else 'no response'}")
        return None

    data = body.get("data")  # type: dict

    trip_ids = []
    for d in data:
        trip_id = d.get("tripId").get("type") + d.get("tripId").get("number")
        trip_ids.append(trip_id)
    return trip_ids


def _query_normal_ticket(place_pair: tuple = ("Nan Jing", "Shang Hai"), headers: dict = {},
                         time: str = "2021-07-15") -> List[str]:
    url = f"{base_address}/api/v1/travel2service/trips/left"
    place_pairs = [("Shang Hai", "Nan Jing"),
                   ("Nan Jing", "Shang Hai")]

    payload = {
        "departureTime": time,
        "startingPlace": place_pair[0],
        "endPlace": place_pair[1],
    }

    response = _request_with_retry("POST", url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    body = _response_json(response)
    if response is None or response.status_code != 200 or body is None or body.get("data") is None:
        logger.warning(f"request for {url} failed. response data is {body if body is not None else (response.text if response is not None else 'no response')}")
        return None

    data = body.get("data")  # type: dict

    trip_ids = []
    for d in data:
        trip_id = d.get("tripId").get("type") + d.get("tripId").get("number")
        trip_ids.append(trip_id)
    return trip_ids


def _query_high_speed_ticket_parallel(place_pair: tuple = ("Shang Hai", "Su Zhou"), headers: dict = {},
                                      time: str = "2021-07-15") -> List[str]:
    """
    返回TripId 列表
    :param place_pair: 使用的开始结束组对
    :param headers: 请求头
    :return: TripId 列表
    """

    url = f"{base_address}/api/v1/travelservice/trips/left_parallel"
    place_pairs = [("Shang Hai", "Su Zhou"),
                   ("Su Zhou", "Shang Hai"),
                   ("Nan Jing", "Shang Hai")]

    payload = {
        "departureTime": time,
        "startingPlace": place_pair[0],
        "endPlace": place_pair[1],
    }

    response = _request_with_retry("POST", url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)

    if response is not None and response.status_code == 405:
        logger.warning(
            f"{url} does not support POST in this deployment, fallback to standard ticket query"
        )
        return _query_high_speed_ticket(place_pair=place_pair, headers=headers, time=time)

    body = _response_json(response)
    if response is None or response.status_code != 200 or body is None or body.get("data") is None:
        logger.warning(f"request for {url} failed. response data is {response.text if response is not None else 'no response'}")
        return None

    data = body.get("data")  # type: dict

    trip_ids = []
    for d in data:
        trip_id = d.get("tripId").get("type") + d.get("tripId").get("number")
        trip_ids.append(trip_id)
    return trip_ids


def _query_advanced_ticket(place_pair: tuple = ("Nan Jing", "Shang Hai"), headers: dict = {}, time: str = "2021-07-15",
                           type: str = "cheapest") -> List[str]:
    url = f"{base_address}/api/v1/travelplanservice/travelPlan/" + type
    print(url)
    timeout = get_env_float("TT_ADVANCED_TIMEOUT", max(REQUEST_TIMEOUT, 45.0))

    payload = {
        "departureTime": time,
        "startingPlace": place_pair[0],
        "endPlace": place_pair[1],
    }

    # print(payload)

    response = _request_with_retry("POST", url, headers=headers, json=payload, timeout=timeout)
    body = _response_json(response)
    if response is None or response.status_code != 200 or body is None or body.get("data") is None:
        logger.warning(f"request for {url} failed. response data is {body if body is not None else (response.text if response is not None else 'no response')}")
        return None

    data = body.get("data")

    trip_ids = []
    for d in data:
        trip_id = d.get("tripId")
        trip_ids.append(trip_id)
    return trip_ids


def _query_assurances(headers: dict = {}):
    url = f"{base_address}/api/v1/assuranceservice/assurances/types"
    response = _request_with_retry("GET", url, headers=headers, timeout=REQUEST_TIMEOUT)
    body = _response_json(response)
    if response is None or response.status_code != 200 or body is None or body.get("data") is None:
        logger.warning(f"query assurance failed, response data is {body if body is not None else (response.text if response is not None else 'no response')}")
        return None
    data = body.get("data")
    # assurance只有一种

    return [{"assurance": "1"}]


def _query_food(place_pair: tuple = ("Shang Hai", "Su Zhou"), train_num: str = "D1345", headers: dict = {},
                date: str = ""):
    if date == "":
        date = get_env_value("TT_TRAVEL_DATE", time.strftime("%Y-%m-%d", time.localtime()))
    url = f"{base_address}/api/v1/foodservice/foods/{date}/{place_pair[0]}/{place_pair[1]}/{train_num}"

    response = _request_with_retry("GET", url, headers=headers, timeout=REQUEST_TIMEOUT)
    body = _response_json(response)
    if response is None or response.status_code != 200 or body is None or body.get("data") is None:
        logger.warning(f"query food failed, response data is {response.text if response is not None else 'no response'}")
        return None
    data = body.get("data")

    # food 是什么不会对后续调用链有影响，因此查询后返回一个固定数值
    return [{
        "foodName": "Soup",
        "foodPrice": 3.7,
        "foodType": 2,
        "stationName": "Su Zhou",
        "storeName": "Roman Holiday"
    }]


def _query_contacts(headers: dict = {}) -> List[str]:
    """
    返回座位id列表
    :param headers:
    :return: id list
    """
    global uuid
    url = f"{base_address}/api/v1/contactservice/contacts/account/{uuid}"

    response = _request_with_retry("GET", url, headers=headers, timeout=REQUEST_TIMEOUT)
    body = _response_json(response)
    if response is None or response.status_code != 200 or body is None or body.get("data") is None:
        logger.warning(f"query contacts failed, response data is {body if body is not None else (response.text if response is not None else 'no response')}")
        return None

    data = body.get("data")
    # print("contacts")
    # pprint(data)

    ids = [d.get("id") for d in data if d.get("id") is not None]
    # pprint(ids)
    return ids


def _query_orders(headers: dict = {}, types: tuple = tuple([0]), query_other: bool = False) -> List[tuple]:
    """
    返回(orderId, tripId) triple list for inside_pay_service
    :param headers:
    :return:
    """
    url = ""

    if query_other:
        url = f"{base_address}/api/v1/orderOtherService/orderOther/refresh"
    else:
        url = f"{base_address}/api/v1/orderservice/order/refresh"

    payload = {
        "loginId": uuid,
    }

    retries = max(1, int(get_env_float("TT_ORDER_QUERY_RETRIES", 3)))
    retry_sleep = get_env_float("TT_ORDER_QUERY_RETRY_SLEEP", 1.0)
    response = None
    last_error = "unknown order query failure"
    for attempt in range(retries):
        try:
            response = requests.post(url=url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200 and response.json().get("data") is not None:
                break
            last_error = response.text
        except requests.RequestException as exc:
            last_error = str(exc)
            response = None

        if attempt + 1 < retries:
            logger.warning(f"query orders attempt {attempt + 1}/{retries} failed for {url}: {last_error}")
            time.sleep(retry_sleep)

    if response is None or response.status_code != 200 or response.json().get("data") is None:
        logger.warning(f"query orders failed, response data is {last_error}")
        return None

    data = response.json().get("data")
    pairs = []
    for d in data:
        # status = 0: not paid
        # status=1 paid not collect
        # status=2 collected
        if d.get("status") in types:
            order_id = d.get("id")
            trip_id = d.get("trainNumber")
            pairs.append((order_id, trip_id))
    print(f"queried {len(pairs)} orders")

    return pairs


def _query_orders_all_info(headers: dict = {}, query_other: bool = False) -> List[tuple]:
    """
    返回(orderId, tripId) triple list for consign service
    :param headers:
    :return:
    """

    if query_other:
        url = f"{base_address}/api/v1/orderOtherService/orderOther/refresh"
    else:
        url = f"{base_address}/api/v1/orderservice/order/refresh"

    payload = {
        "loginId": uuid,
    }

    retries = max(1, int(get_env_float("TT_ORDER_QUERY_RETRIES", 3)))
    retry_sleep = get_env_float("TT_ORDER_QUERY_RETRY_SLEEP", 1.0)
    response = None
    last_error = "unknown order query failure"
    for attempt in range(retries):
        try:
            response = requests.post(url=url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200 and response.json().get("data") is not None:
                break
            last_error = response.text
        except requests.RequestException as exc:
            last_error = str(exc)
            response = None

        if attempt + 1 < retries:
            logger.warning(f"query orders all info attempt {attempt + 1}/{retries} failed for {url}: {last_error}")
            time.sleep(retry_sleep)

    if response is None or response.status_code != 200 or response.json().get("data") is None:
        logger.warning(f"query orders failed, response data is {last_error}")
        return None

    data = response.json().get("data")
    pairs = []
    for d in data:
        result = {}
        result["accountId"] = d.get("accountId")
        result["targetDate"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        result["orderId"] = d.get("id")
        result["from"] = d.get("from")
        result["to"] = d.get("to")
        pairs.append(result)
    print(f"queried {len(pairs)} orders")

    return pairs


def _put_consign(result, headers: dict = {}):
    url = f"{base_address}/api/v1/consignservice/consigns"
    consignload = {
        "accountId": result["accountId"],
        "handleDate": time.strftime('%Y-%m-%d', time.localtime(time.time())),
        "targetDate": result["targetDate"],
        "from": result["from"],
        "to": result["to"],
        "orderId": result["orderId"],
        "consignee": get_env_value("TT_CONSIGN_CONSIGNEE", "consignee"),
        "phone": get_env_value("TT_CONSIGN_PHONE", "12345677654"),
        "weight": get_env_value("TT_CONSIGN_WEIGHT", "32"),
        "id": "",
        "isWithin": False
    }
    response = _request_with_retry("PUT", url, headers=headers, json=consignload, timeout=REQUEST_TIMEOUT)

    order_id = result["orderId"]
    if response is not None and response.status_code in (200, 201):
        print(f"{order_id} put consign success")
    else:
        print(f"{order_id} failed! status={response.status_code if response is not None else 'no response'} body={response.text if response is not None else 'no response'}")
        return None

    return order_id


def _query_route(routeId: str = '92708982-77af-4318-be25-57ccb0ff69ad', headers: dict = {}):
    url = f"{base_address}/api/v1/routeservice/routes/{routeId}"

    res = _request_with_retry("GET", url, headers=headers, timeout=REQUEST_TIMEOUT)
    body = _response_json(res)

    if res is not None and res.status_code == 200 and body is not None:
        print(f"query {routeId} success")
        return body.get("data")

    print(f"query {routeId} fail")
    return None


def _pay_one_order(order_id, trip_id, headers: dict = {}):
    url = f"{base_address}/api/v1/inside_pay_service/inside_payment"
    payload = {
        "orderId": order_id,
        "tripId": trip_id
    }

    response = _request_with_retry("POST", url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)

    if response is not None and response.status_code == 200:
        print(f"{order_id} pay success")
    else:
        print(f"pay {order_id} failed! status={response.status_code if response is not None else 'no response'} body={response.text if response is not None else 'no response'}")
        return None

    return order_id


def _cancel_one_order(order_id, uuid, headers: dict = {}):
    url = f"{base_address}/api/v1/cancelservice/cancel/{order_id}/{uuid}"

    response = _request_with_retry("GET", url, headers=headers, timeout=REQUEST_TIMEOUT)

    if response is not None and response.status_code == 200:
        print(f"{order_id} cancel success")
    else:
        print(f"{order_id} cancel failed. status={response.status_code if response is not None else 'no response'} body={response.text if response is not None else 'no response'}")
        return None

    return order_id


def _collect_one_order(order_id, headers: dict = {}):
    url = f"{base_address}/api/v1/executeservice/execute/collected/{order_id}"
    response = _request_with_retry("GET", url, headers=headers, timeout=REQUEST_TIMEOUT)
    if response is not None and response.status_code == 200:
        print(f"{order_id} collect success")
    else:
        print(f"{order_id} collect failed. status={response.status_code if response is not None else 'no response'} body={response.text if response is not None else 'no response'}")
        return None

    return order_id


def _enter_station(order_id, headers: dict = {}):
    url = f"{base_address}/api/v1/executeservice/execute/execute/{order_id}"
    response = _request_with_retry("GET", url, headers=headers, timeout=REQUEST_TIMEOUT)
    if response is not None and response.status_code == 200:
        print(f"{order_id} enter station success")
    else:
        print(f"{order_id} enter station failed. status={response.status_code if response is not None else 'no response'} body={response.text if response is not None else 'no response'}")
        return None

    return order_id


def _query_cheapest(date="2021-12-31", headers: dict = {}):
    url = f"{base_address}/api/v1/travelplanservice/travelPlan/cheapest"

    payload = {
        "departureTime": date,
        "endPlace": "Shang Hai",
        "startingPlace": "Nan Jing"
    }

    r = requests.post(url=url, json=payload, headers=headers)
    if r.status_code == 200:
        print("query cheapest success")
    else:
        print("query cheapest failed")


def _query_min_station(date="2021-12-31", headers: dict = {}):
    url = f"{base_address}/api/v1/travelplanservice/travelPlan/minStation"

    payload = {
        "departureTime": date,
        "endPlace": "Shang Hai",
        "startingPlace": "Nan Jing"
    }

    r = requests.post(url=url, json=payload, headers=headers)
    if r.status_code == 200:
        print("query min station success")
    else:
        print("query min station failed")


def _query_quickest(date="2021-12-31", headers: dict = {}):
    url = f"{base_address}/api/v1/travelplanservice/travelPlan/quickest"

    payload = {
        "departureTime": date,
        "endPlace": "Shang Hai",
        "startingPlace": "Nan Jing"
    }

    r = requests.post(url=url, json=payload, headers=headers)
    if r.status_code == 200:
        print("query quickest success")
    else:
        print("query quickest failed")


def _query_admin_basic_price(headers: dict = {}):
    url = f"{base_address}/api/v1/adminbasicservice/adminbasic/prices"
    response = _request_with_retry("GET", url, headers=headers, timeout=REQUEST_TIMEOUT)
    if response is not None and response.status_code == 200:
        print(f"price success")
        return response
    else:
        print(f"price failed")
        return None


def _query_admin_basic_config(headers: dict = {}):
    url = f"{base_address}/api/v1/adminbasicservice/adminbasic/configs"
    response = _request_with_retry("GET", url, headers=headers, timeout=REQUEST_TIMEOUT)
    if response is not None and response.status_code == 200:
        print(f"config success")
        return response
    else:
        print(f"config failed")
        return None


def _rebook_ticket(old_order_id, old_trip_id, new_trip_id, new_date, new_seat_type, headers):
    url = f"{base_address}/api/v1/rebookservice/rebook"

    payload = {
        "oldTripId": old_trip_id,
        "orderId": old_order_id,
        "tripId": new_trip_id,
        "date": new_date,
        "seatType": new_seat_type
    }
    print(payload)
    r = _request_with_retry("POST", url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    if r is None or r.status_code != 200:
        print(f"Request Failed: status code: {r.status_code if r is not None else 'no response'}")
        print(r.text if r is not None else "no response")
        return None

    body = _response_json(r)
    if body is None:
        print(f"Request Failed: invalid json body: {r.text}")
        return None

    print(r.text)
    if body.get("status") != 1:
        print(f"rebook business failed: {body}")
        return None
    return old_order_id


def _query_admin_travel(headers):
    url = f"{base_address}/api/v1/admintravelservice/admintravel"

    r = requests.get(url=url, headers=headers)
    if r.status_code == 200 and r.json()["status"] == 1:
        print("success to query admin travel")
    else:
        print(f"faild to query admin travel with status_code: {r.status_code}")


if __name__ == '__main__':
    _, token = _login(username="admin", password="222222")
    print(token)
