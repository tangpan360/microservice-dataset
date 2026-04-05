from __future__ import annotations

from tt_injector.core.auth import AuthSession
from tt_injector.core.http import HttpClient
from tt_injector.core.models import ActionResult


def query_admin_basic_price(client: HttpClient, auth: AuthSession) -> ActionResult:
    response = client.request("GET", "/api/v1/adminbasicservice/adminbasic/prices", headers=auth.headers())
    ok = response.status_code == 200
    return ActionResult(ok=ok, name="queryAdminBasicPrice", detail=response.text)


def query_admin_basic_config(client: HttpClient, auth: AuthSession) -> ActionResult:
    response = client.request("GET", "/api/v1/adminbasicservice/adminbasic/configs", headers=auth.headers())
    ok = response.status_code == 200
    return ActionResult(ok=ok, name="queryAdminBasicConfig", detail=response.text)
