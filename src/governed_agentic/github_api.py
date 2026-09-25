"""Snapshot interface; this reference application does not mutate GitHub."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from .security import AdmissionError


@dataclass(frozen=True)
class RepositorySnapshot:
    repository: str
    sha: str
    exists: bool


class GitHubSnapshotPort(Protocol):
    async def get_commit(self, repository: str, sha: str) -> RepositorySnapshot: ...


class MockGitHubAPI:
    def __init__(self, repository: str = "example/workflow-demo", sha: str = "a" * 40):
        self.repository = repository
        self.sha = sha

    async def get_commit(self, repository: str, sha: str) -> RepositorySnapshot:
        if repository != self.repository or sha != self.sha:
            raise AdmissionError("SNAPSHOT_MISMATCH")
        return RepositorySnapshot(repository, sha, True)


class GitHubReadOnlyAPI:
    """Optional read-only REST implementation; uses no private connector implementation."""

    def __init__(self, expected_repository: str, token: str, timeout_seconds: float = 5.0):
        from .events import REPOSITORY_RE
        if not REPOSITORY_RE.fullmatch(expected_repository):
            raise ValueError("invalid expected repository")
        if not token or not 0 < timeout_seconds <= 30:
            raise ValueError("token and bounded timeout required")
        self.expected_repository = expected_repository
        self.token = token
        self.timeout_seconds = timeout_seconds

    async def get_commit(self, repository: str, sha: str) -> RepositorySnapshot:
        import asyncio
        import json
        from urllib.parse import quote
        from urllib.request import Request, urlopen
        from .events import SHA_RE
        if repository != self.expected_repository or not SHA_RE.fullmatch(sha):
            raise AdmissionError("SNAPSHOT_REQUEST_NOT_ALLOWED")
        url = ("https://api.github.com/repos/"
               + quote(self.expected_repository, safe="/") + "/commits/" + sha)

        def fetch():
            request = Request(url, headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "governed-agentic-reference",
            })
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.load(response)

        try:
            result = await asyncio.wait_for(asyncio.to_thread(fetch), self.timeout_seconds + 1)
        except Exception:
            raise AdmissionError("GITHUB_SNAPSHOT_UNAVAILABLE") from None
        if not isinstance(result, dict) or result.get("sha") != sha:
            raise AdmissionError("SNAPSHOT_MISMATCH")
        return RepositorySnapshot(repository, sha, True)
