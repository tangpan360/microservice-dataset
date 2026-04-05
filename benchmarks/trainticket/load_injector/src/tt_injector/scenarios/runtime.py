from __future__ import annotations

from dataclasses import dataclass, field

from tt_injector.core.auth import AuthSession, login_admin, login_user
from tt_injector.core.context import RuntimeContext
from tt_injector.core.http import HttpClient


@dataclass(slots=True)
class ScenarioRuntime:
    context: RuntimeContext
    client: HttpClient = field(init=False)
    _user_auth: AuthSession | None = field(default=None, init=False, repr=False)
    _admin_auth: AuthSession | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.client = HttpClient(self.context)

    @property
    def user_auth(self) -> AuthSession:
        if self._user_auth is None:
            self._user_auth = login_user(self.client, self.context)
        return self._user_auth

    @property
    def admin_auth(self) -> AuthSession:
        if self._admin_auth is None:
            self._admin_auth = login_admin(self.client, self.context)
        return self._admin_auth

    @classmethod
    def create(cls, context: RuntimeContext) -> "ScenarioRuntime":
        return cls(context=context)
