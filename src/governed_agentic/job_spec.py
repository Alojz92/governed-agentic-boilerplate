"""Deterministic matching of *already extracted* requirements against approved public capability data."""
from __future__ import annotations
from typing import Any

ALLOWED_STATUSES = {"SUPPORTED", "TRANSFERABLE", "GAP", "UNKNOWN"}


def match_requirements(requirements: list[dict[str, str]], capabilities: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in requirements:
        cap = str(item.get("capability", ""))
        source = capabilities.get(cap, {})
        status = source.get("status", "UNKNOWN")
        if status not in ALLOWED_STATUSES:
            status = "UNKNOWN"
        refs = source.get("evidence_refs", [])
        if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
            refs = []
        if status in {"SUPPORTED", "TRANSFERABLE"} and not refs:
            status = "UNKNOWN"
        rows.append({"requirement_id": str(item.get("id", ""))[:40],
                     "requirement": str(item.get("text", ""))[:400],
                     "status": status, "evidence_refs": refs if status in {"SUPPORTED", "TRANSFERABLE"} else [],
                     "limitation": str(source.get("limitation", "Not established by approved public evidence"))[:240]})
    return rows
