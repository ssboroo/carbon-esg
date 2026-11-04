"""Local MCP adapter for AI clients.

First release: public registry reads and deterministic Scope 1/2 previews only.
No tenant data, database connection, mutation, or file tools are exposed.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from .calculator import calculate_inventory
from .schemas import InventoryCalculationRequest

mcp = FastMCP(
    "Carbon ESG",
    instructions=(
        "Use deterministic Scope 1/2 calculation previews and read-only "
        "Mongolian legal and standards catalogues. Never invent emission "
        "factors or legal requirements. Factor provenance is mandatory. "
        "Calculation outputs are previews, not approved inventory submissions."
    ),
)

API_BASE_URL = os.getenv("CARBON_ESG_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.getenv("CARBON_ESG_API_TOKEN", "")


def _get_api(path: str) -> Any:
    """Call a fixed local API path; never accept caller-provided URLs."""
    headers = {"Accept": "application/json"}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    try:
        response = httpx.get(
            f"{API_BASE_URL}{path}", headers=headers, timeout=10.0
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Carbon ESG API returned HTTP {exc.response.status_code} for {path}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(
            "Carbon ESG API is unavailable. Start it and check CARBON_ESG_API_URL."
        ) from exc


@mcp.tool()
def carbon_esg_health() -> dict[str, Any]:
    """Check whether the configured Carbon ESG API is reachable."""
    return _get_api("/health")


@mcp.tool()
def calculate_scope12_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate a Scope 1/2 preview from activity data and sourced factors.

    Payload requires reporting_period_start, reporting_period_end and records.
    Every record must include a positive activity amount, matching activity
    and factor units, non-negative factor, HTTPS source URL, source year and
    version. No default or AI-generated factors are used.
    """
    request = InventoryCalculationRequest.model_validate(payload)
    return calculate_inventory(request).model_dump(mode="json")


@mcp.tool()
def search_mongolia_legal_registry(keyword: str = "") -> list[dict[str, Any]]:
    """Search the imported Mongolian legal-act metadata index."""
    rows = _get_api("/v1/legal/acts")
    term = keyword.strip().casefold()
    if not term:
        return rows
    return [
        row for row in rows
        if any(term in str(row.get(field, "")).casefold()
               for field in ("title", "code", "status"))
    ]


@mcp.tool()
def list_esg_standards(keyword: str = "") -> list[dict[str, Any]]:
    """Search ESG standards metadata; copyrighted full text is not distributed."""
    rows = _get_api("/v1/standards")
    term = keyword.strip().casefold()
    if not term:
        return rows
    return [
        row for row in rows
        if any(term in str(row.get(field, "")).casefold()
               for field in ("title", "code", "status"))
    ]


def main() -> None:
    """Run the local stdio MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
