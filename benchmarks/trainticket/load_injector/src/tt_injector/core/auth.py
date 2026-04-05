from __future__ import annotations

from dataclasses import dataclass

from .context import RuntimeContext
from .http import HttpClient


@dataclass(slots=True)
class AuthSession:
    user_id: str
    token: str

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Connection": "close",
        }


def login_user(client: HttpClient, context: RuntimeContext) -> AuthSession:
    response = client.request(
        "POST",
        "/api/v1/users/login",
        json_data={
            "username": context.username,
            "password": context.password,
            "verificationCode": "",
        },
    )
    body = response.body or {}
    data = body.get("data") or {}
    if response.status_code != 200 or body.get("status") != 1 or not data.get("userId") or not data.get("token"):
        raise RuntimeError(f"普通用户登录失败: {response.text}")
    return AuthSession(user_id=data["userId"], token=data["token"])


def login_admin(client: HttpClient, context: RuntimeContext) -> AuthSession:
    response = client.request(
        "POST",
        "/api/v1/users/login",
        json_data={
            "username": context.admin_username,
            "password": context.admin_password,
            "verificationCode": "",
        },
    )
    body = response.body or {}
    data = body.get("data") or {}
    if response.status_code != 200 or body.get("status") != 1 or not data.get("userId") or not data.get("token"):
        raise RuntimeError(f"管理员登录失败: {response.text}")
    return AuthSession(user_id=data["userId"], token=data["token"])
