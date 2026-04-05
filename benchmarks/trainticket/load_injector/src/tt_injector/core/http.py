from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from .context import RuntimeContext

logger = logging.getLogger("tt_injector.http")


@dataclass(slots=True)
class HttpResponse:
    status_code: int | None
    body: dict[str, Any] | None
    text: str


class HttpClient:
    def __init__(self, context: RuntimeContext):
        self.context = context
        self.session = requests.Session()

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        url = f"{self.context.base_url}{path}"
        timeout = self.context.timeout if timeout is None else timeout
        last_error = "unknown request failure"

        response = None
        for attempt in range(self.context.request_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    timeout=timeout,
                )
                if response.status_code < 500:
                    return self._wrap(response)
                last_error = f"status={response.status_code} body={response.text}"
            except requests.RequestException as exc:
                response = None
                last_error = str(exc)

            if attempt + 1 < self.context.request_retries:
                logger.warning("%s %s transient failure %s/%s: %s", method, url, attempt + 1, self.context.request_retries, last_error)
                time.sleep(self.context.retry_sleep)

        if response is None:
            logger.warning("%s %s failed after %s attempts: %s", method, url, self.context.request_retries, last_error)
            return HttpResponse(status_code=None, body=None, text=last_error)
        return self._wrap(response)

    @staticmethod
    def _wrap(response: requests.Response) -> HttpResponse:
        body = None
        try:
            body = response.json()
        except ValueError:
            body = None
        return HttpResponse(status_code=response.status_code, body=body, text=response.text)
