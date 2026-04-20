from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import httpx


class AshriseApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Ashrise API error {status_code}: {detail}")


@dataclass(frozen=True)
class AshriseApiSettings:
    base_url: str
    token: str
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "AshriseApiSettings":
        base_url = os.getenv("ASHRISE_BASE_URL")
        token = os.getenv("ASHRISE_TOKEN")

        if not base_url:
            raise RuntimeError("Missing required environment variable ASHRISE_BASE_URL")
        if not token:
            raise RuntimeError("Missing required environment variable ASHRISE_TOKEN")

        return cls(base_url=base_url.rstrip("/"), token=token)


class AshriseApiClient:
    def __init__(
        self,
        settings: AshriseApiSettings | None = None,
        client: httpx.Client | None = None,
    ):
        self.settings = settings or AshriseApiSettings.from_env()
        self._owns_client = client is None
        self.client = client or httpx.Client(
            base_url=self.settings.base_url,
            headers={"Authorization": f"Bearer {self.settings.token}"},
            timeout=self.settings.timeout,
        )

    def close(self):
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "AshriseApiClient":
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def request_json(
        self,
        method: str,
        path: str,
        *,
        allow_404: bool = False,
        **kwargs,
    ) -> Any:
        response = self.client.request(method, path, **kwargs)
        if allow_404 and response.status_code == 404:
            return None

        if response.is_error:
            detail = response.text
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict) and payload.get("detail"):
                detail = str(payload["detail"])
            raise AshriseApiError(response.status_code, detail)

        if response.status_code == 204 or not response.content:
            return None

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()

        return response.text

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/runs", json=payload)

    def patch_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("PATCH", f"/runs/{run_id}", json=payload)

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self.request_json("GET", f"/projects/{project_id}")

    def list_projects(self, **params) -> list[dict[str, Any]]:
        return self.request_json("GET", "/projects", params=params)

    def get_state(self, project_id: str, *, allow_404: bool = False) -> dict[str, Any] | None:
        return self.request_json("GET", f"/state/{project_id}", allow_404=allow_404)

    def put_state(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("PUT", f"/state/{project_id}", json=payload)

    def get_audit(self, project_id: str) -> dict[str, Any] | None:
        return self.request_json("GET", f"/audit/{project_id}", allow_404=False)

    def get_handoffs(self, project_id: str, status: str = "open") -> list[dict[str, Any]]:
        return self.request_json("GET", f"/handoffs/{project_id}", params={"status": status})

    def create_handoff(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/handoffs", json=payload)

    def create_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/decisions", json=payload)

    def get_runs(self, project_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.request_json("GET", f"/runs/{project_id}", params={"limit": limit})

    def create_idea(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/ideas", json=payload)

    def list_candidates(self, **params) -> list[dict[str, Any]]:
        query = {key: value for key, value in params.items() if value is not None}
        return self.request_json("GET", "/candidates", params=query)

    def get_candidate(self, candidate_ref: str) -> dict[str, Any]:
        return self.request_json("GET", f"/candidates/{candidate_ref}")

    def get_candidate_research(self, candidate_ref: str) -> dict[str, Any] | None:
        return self.request_json(
            "GET",
            f"/candidates/{candidate_ref}/research",
            allow_404=False,
        )

    def get_research_queue(self, due: str | None = None) -> list[dict[str, Any]]:
        params = {"due": due} if due else None
        return self.request_json("GET", "/research-queue", params=params)

    def patch_research_queue(self, queue_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("PATCH", f"/research-queue/{queue_id}", json=payload)

    def patch_candidate(self, candidate_ref: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("PATCH", f"/candidates/{candidate_ref}", json=payload)

    def promote_candidate(self, candidate_ref: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", f"/candidates/{candidate_ref}/promote", json=payload)

    def run_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/agent/run", json=payload)
