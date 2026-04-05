from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TicketQuery:
    start: str
    end: str
    date: str
    high_speed: bool


@dataclass(slots=True)
class PreserveOptions:
    start: str
    end: str
    date: str
    high_speed: bool
    preferred_trip_id: str | None = None
    need_food: bool = False
    need_assurance: bool = False
    need_consign: bool = False
    force_new_order: bool = False


@dataclass(slots=True)
class OrderRecord:
    order_id: str
    trip_id: str
    status: int
    account_id: str | None = None
    from_station: str | None = None
    to_station: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActionResult:
    ok: bool
    name: str
    detail: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
