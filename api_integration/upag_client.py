"""Client for the documented UPAg Data Share API."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx


class UPAgAPIError(RuntimeError):
    pass


class UPAgClient:
    LOGIN_PATH = "/v1/upag/api-data-share/login"

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("UPAG_BASE_URL", "https://data.upag.gov.in")).rstrip("/")
        self.username = username if username is not None else os.getenv("UPAG_USER", "")
        self.password = password if password is not None else os.getenv("UPAG_PASSWORD", "")
        self.timeout = timeout
        self.retries = max(1, retries)
        self._client = client or httpx.Client(timeout=timeout)
        self._token: str | None = None

    @property
    def credentials_configured(self) -> bool:
        return bool(self.username and self.password)

    def login(self) -> str:
        if not self.credentials_configured:
            raise UPAgAPIError("UPAg credentials are not configured; set UPAG_USER and UPAG_PASSWORD")
        response = self._request("POST", self.LOGIN_PATH, data={"username": self.username, "password": self.password})
        try:
            payload = response.json()
            token = payload["access_token"]
        except (ValueError, KeyError, TypeError) as error:
            raise UPAgAPIError("UPAg login response did not contain an access token") from error
        if not isinstance(token, str) or not token:
            raise UPAgAPIError("UPAg login returned an empty access token")
        self._token = token
        return token

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, data: Any = None, json_body: Any = None) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token and path != self.LOGIN_PATH else {}
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self._client.request(
                    method,
                    f"{self.base_url}{path}",
                    params=params,
                    data=data,
                    json=json_body,
                    headers=headers,
                )
                if response.status_code == 401 and path != self.LOGIN_PATH and self.credentials_configured:
                    self._token = None
                    self.login()
                    headers = {"Authorization": f"Bearer {self._token}"}
                    response = self._client.request(method, f"{self.base_url}{path}", params=params, json=json_body, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < self.retries:
                        retry_after = response.headers.get("Retry-After")
                        delay = min(float(retry_after), 10.0) if retry_after and retry_after.isdigit() else 0.5 * (2**attempt)
                        time.sleep(delay)
                        continue
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as error:
                status = error.response.status_code
                if status < 500 and status != 429:
                    raise UPAgAPIError(f"UPAg request failed with HTTP {status}") from error
                last_error = error
            except httpx.HTTPError as error:
                last_error = error
                if attempt + 1 < self.retries:
                    time.sleep(0.5 * (2**attempt))
        raise UPAgAPIError(f"UPAg request failed after {self.retries} attempts: {type(last_error).__name__ if last_error else 'unknown error'}")

    def _authorized(self) -> None:
        if not self._token:
            self.login()

    def allowed_sources(self) -> list[Any]:
        self._authorized()
        response = self._request("GET", "/v1/upag/api-data-share/sources/user-allowed-sources")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("allowedSources"), list):
            raise UPAgAPIError("UPAg allowed-sources response has an unexpected schema")
        return payload["allowedSources"]

    def fetch_source(self, source_name: str, source_input: dict[str, Any], *, page_size: int = 1000, max_pages: int = 1000) -> list[dict[str, Any]]:
        """Read a documented source endpoint using its limit/offset schema."""
        if not 1 <= page_size <= 10000:
            raise ValueError("page_size must be between 1 and 10000")
        self._authorized()
        records: list[dict[str, Any]] = []
        offset = 0
        for _ in range(max_pages):
            page_input = {**source_input, "source_name": source_name, "limit": page_size, "offset": offset}
            response = self._request("POST", f"/v1/upag/api-data-share/sources/{source_name}", json_body={"source_input_object": page_input})
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("status") != "Success" or not isinstance(payload.get("data"), list):
                raise UPAgAPIError("UPAg source response was unsuccessful or did not match the documented schema")
            page = payload["data"]
            records.extend(row for row in page if isinstance(row, dict))
            total = payload.get("totalRecords")
            offset += len(page)
            if not page or (isinstance(total, int) and offset >= total) or len(page) < page_size:
                return records
        raise UPAgAPIError(f"UPAg pagination stopped at max_pages={max_pages}; partial results were not returned")

    def statewise_apy(self, filters: dict[str, Any]) -> Any:
        self._authorized()
        return self._request("POST", "/v1/upag/api-data-share/apy/statewise", json_body=filters).json()

    def districtwise_apy(self, filters: dict[str, Any]) -> Any:
        self._authorized()
        return self._request("POST", "/v1/upag/api-data-share/apy/districtwise", json_body=filters).json()

    def apy_filters(self, **requested: bool) -> Any:
        self._authorized()
        allowed = {"crops", "states", "seasons", "crop_categories", "metrics", "uoms"}
        params = {key: bool(value) for key, value in requested.items() if key in allowed}
        return self._request("GET", "/v1/upag/api-data-share/apy/filter", params=params).json()

    def crop_master(self) -> Any:
        self._authorized()
        return self._request("GET", "/v1/upag/api-data-share/crop/master").json()

    def crop_production(self, crop_year: str) -> Any:
        self._authorized()
        return self._request("POST", "/v1/upag/api-data-share/crop/production", params={"crop_year": crop_year}).json()
