from __future__ import annotations

from typing import Any

from tt_injector.core.auth import AuthSession
from tt_injector.core.helpers import random_pick
from tt_injector.core.http import HttpClient
from tt_injector.core.models import ActionResult, TicketQuery


def search_tickets(client: HttpClient, auth: AuthSession, query: TicketQuery) -> ActionResult:
    path = "/api/v1/travelservice/trips/left" if query.high_speed else "/api/v1/travel2service/trips/left"
    response = client.request(
        "POST",
        path,
        headers=auth.headers(),
        json_data={
            "departureTime": query.date,
            "startingPlace": query.start,
            "endPlace": query.end,
        },
    )
    body = response.body or {}
    data = body.get("data") or []
    trip_ids = []
    for item in data:
        trip = item.get("tripId") or {}
        number = trip.get("number")
        trip_type = trip.get("type")
        if number and trip_type:
            trip_ids.append(f"{trip_type}{number}")
    return ActionResult(ok=bool(trip_ids), name="searchTickets", detail=response.text, payload={"trip_ids": trip_ids})


def search_parallel_tickets(client: HttpClient, auth: AuthSession, query: TicketQuery) -> ActionResult:
    response = client.request(
        "POST",
        "/api/v1/travelservice/trips/left_parallel",
        headers=auth.headers(),
        json_data={
            "departureTime": query.date,
            "startingPlace": query.start,
            "endPlace": query.end,
        },
    )
    if response.status_code == 405:
        return search_tickets(client, auth, query)
    body = response.body or {}
    data = body.get("data") or []
    trip_ids = []
    for item in data:
        trip = item.get("tripId") or {}
        number = trip.get("number")
        trip_type = trip.get("type")
        if number and trip_type:
            trip_ids.append(f"{trip_type}{number}")
    return ActionResult(ok=bool(trip_ids), name="searchParallelTickets", detail=response.text, payload={"trip_ids": trip_ids})


def query_route(client: HttpClient, auth: AuthSession, route_id: str) -> ActionResult:
    response = client.request("GET", f"/api/v1/routeservice/routes/{route_id}", headers=auth.headers())
    ok = response.status_code == 200 and response.body is not None
    return ActionResult(ok=ok, name="queryRoute", detail=response.text, payload={"route": (response.body or {}).get("data")})


def query_food(
    client: HttpClient,
    auth: AuthSession,
    *,
    date: str,
    start: str,
    end: str,
    trip_id: str,
) -> ActionResult:
    response = client.request(
        "GET",
        f"/api/v1/foodservice/foods/{date}/{start}/{end}/{trip_id}",
        headers=auth.headers(),
    )
    body = response.body or {}
    data = body.get("data") or {}
    train_food_list = data.get("trainFoodList") or []
    store_food_map = data.get("foodStoreListMap") or {}
    ok = (
        response.status_code == 200
        and body.get("status") == 1
        and (bool(train_food_list) or bool(store_food_map))
    )
    return ActionResult(
        ok=ok,
        name="queryFood",
        detail=response.text,
        payload={
            "foods": data,
            "train_food_list": train_food_list,
            "food_store_map": store_food_map,
        },
    )


def query_advanced_plan(client: HttpClient, auth: AuthSession, *, date: str, start: str, end: str, plan_type: str) -> ActionResult:
    response = client.request(
        "POST",
        f"/api/v1/travelplanservice/travelPlan/{plan_type}",
        headers=auth.headers(),
        json_data={
            "departureTime": date,
            "startingPlace": start,
            "endPlace": end,
        },
        timeout=max(client.context.timeout, 45.0),
    )
    body = response.body or {}
    data = body.get("data") or []
    return ActionResult(ok=bool(data), name="queryAdvancedPlan", detail=response.text, payload={"trip_ids": [item.get("tripId") for item in data]})


def query_contacts(client: HttpClient, auth: AuthSession) -> ActionResult:
    response = client.request("GET", f"/api/v1/contactservice/contacts/account/{auth.user_id}", headers=auth.headers())
    body = response.body or {}
    data = body.get("data") or []
    contact_ids = [item.get("id") for item in data if item.get("id")]
    return ActionResult(ok=bool(contact_ids), name="queryContacts", detail=response.text, payload={"contact_ids": contact_ids})


def query_assurance_types(client: HttpClient, auth: AuthSession) -> ActionResult:
    response = client.request("GET", "/api/v1/assuranceservice/assurances/types", headers=auth.headers())
    body = response.body or {}
    data = body.get("data") or []
    return ActionResult(ok=bool(data), name="queryAssuranceTypes", detail=response.text, payload={"assurance_types": data})


def pick_trip_id(result: ActionResult, rng) -> str | None:
    trip_ids = result.payload.get("trip_ids") or []
    if not trip_ids:
        return None
    return random_pick(rng, trip_ids)
