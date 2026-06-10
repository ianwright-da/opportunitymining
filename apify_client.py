"""Apify REST API client for johnvc/google-forums-search-api."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import requests

ACTOR_ID = "johnvc/google-forums-search-api"
APIFY_API_BASE = "https://api.apify.com/v2"
TRANSIENT_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


class ApifyError(RuntimeError):
    """Raised when an Apify actor run fails or cannot be read."""


class ApifyClient:
    """Small requests-based client for running the Apify actor and reading items."""

    def __init__(
        self,
        token: str,
        timeout_seconds: int = 60,
        max_retries: int = 4,
        poll_interval_seconds: float = 5.0,
        max_poll_seconds: int = 900,
    ):
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.poll_interval_seconds = poll_interval_seconds
        self.max_poll_seconds = max_poll_seconds
        self.session = requests.Session()

    def search_forums(self, query: str) -> list[dict[str, Any]]:
        """Run the forum search actor for a query and return dataset items."""

        run = self._start_actor_run(query)
        run = self._wait_for_completion(run)

        status = run.get("status")
        if status != "SUCCEEDED":
            raise ApifyError(f"Actor run ended with status {status or 'UNKNOWN'}")

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            raise ApifyError("Actor run succeeded but did not include defaultDatasetId")

        return self._fetch_dataset_items(dataset_id)

    def _start_actor_run(self, query: str) -> dict[str, Any]:
        encoded_actor_id = quote(ACTOR_ID, safe="")
        url = f"{APIFY_API_BASE}/acts/{encoded_actor_id}/runs"
        payload = {
            "q": query,
            "device": "desktop",
            "safe": "off",
            "nfpr": "0",
            "filter": "0",
            "max_pages": 0,
        }
        response = self._request("POST", url, json=payload)
        data = response.json()
        return data.get("data", data)

    def _wait_for_completion(self, run: dict[str, Any]) -> dict[str, Any]:
        status = run.get("status")
        run_id = run.get("id")
        if status in TERMINAL_STATUSES:
            return run
        if not run_id:
            raise ApifyError("Actor run response did not include an id")

        deadline = time.monotonic() + self.max_poll_seconds
        while time.monotonic() < deadline:
            time.sleep(self.poll_interval_seconds)
            response = self._request("GET", f"{APIFY_API_BASE}/actor-runs/{run_id}")
            data = response.json()
            run = data.get("data", data)
            status = run.get("status")
            if status in TERMINAL_STATUSES:
                return run

        raise ApifyError(f"Timed out waiting for actor run {run_id} to finish")

    def _fetch_dataset_items(self, dataset_id: str) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"{APIFY_API_BASE}/datasets/{dataset_id}/items",
            params={"clean": "true", "format": "json"},
        )
        items = response.json()
        if not isinstance(items, list):
            raise ApifyError("Dataset items response was not a JSON list")
        return [item for item in items if isinstance(item, dict)]

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=self.timeout_seconds,
                    **kwargs,
                )
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise ApifyError(f"HTTP request failed: {exc}") from exc
                self._sleep_before_retry(attempt)
                continue

            if response.status_code not in TRANSIENT_STATUS_CODES:
                try:
                    response.raise_for_status()
                except requests.HTTPError as exc:
                    raise ApifyError(
                        f"Apify API returned HTTP {response.status_code}: {response.text[:500]}"
                    ) from exc
                return response

            if attempt >= self.max_retries:
                raise ApifyError(
                    f"Apify API returned transient HTTP {response.status_code} after retries: "
                    f"{response.text[:500]}"
                )
            self._sleep_before_retry(attempt)

        raise ApifyError("Unreachable retry state")

    @staticmethod
    def _sleep_before_retry(attempt: int) -> None:
        delay = min(2**attempt, 30)
        time.sleep(delay)
