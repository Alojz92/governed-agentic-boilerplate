"""Deterministic GitHub event parser; event fields are never executable authority."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from .security import AdmissionError

REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[a-fA-F0-9]{40}$")
ALLOWED_EVENTS = {"push", "pull_request"}
ALLOWED_PR_ACTIONS = {"opened", "synchronize"}


@dataclass(frozen=True)
class AdmittedEvent:
    delivery_id: str
    kind: str
    repository: str
    commit_sha: str
    branch: str


def admit_event(payload: Any, kind: str, delivery_id: str, expected_repository: str) -> AdmittedEvent:
    if kind not in ALLOWED_EVENTS:
        raise AdmissionError("UNSUPPORTED_EVENT")
    if not REPOSITORY_RE.fullmatch(expected_repository):
        raise AdmissionError("INVALID_CONFIGURATION")
    if not isinstance(payload, dict) or not isinstance(payload.get("repository"), dict):
        raise AdmissionError("INVALID_PAYLOAD")
    repository = payload["repository"].get("full_name")
    if repository != expected_repository:
        raise AdmissionError("REPOSITORY_NOT_ALLOWED")
    if kind == "push":
        if payload.get("ref") != "refs/heads/main" or payload.get("deleted") is True:
            raise AdmissionError("BRANCH_NOT_ALLOWED")
        sha = payload.get("after")
    else:
        if payload.get("action") not in ALLOWED_PR_ACTIONS:
            raise AdmissionError("ACTION_NOT_ALLOWED")
        pr = payload.get("pull_request")
        if not isinstance(pr, dict) or not isinstance(pr.get("head"), dict):
            raise AdmissionError("INVALID_PAYLOAD")
        head = pr["head"]
        if not isinstance(head.get("repo"), dict) or head["repo"].get("full_name") != expected_repository:
            raise AdmissionError("FORK_NOT_ALLOWED")
        sha = head.get("sha")
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise AdmissionError("INVALID_COMMIT_SHA")
    return AdmittedEvent(delivery_id, kind, repository, sha.lower(), "main" if kind == "push" else "pull_request")
