"""Bounded asynchronous routing with process-local idempotency and safe traces."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, asdict
from .events import AdmittedEvent
from .executor import DesktopCommanderPort
from .github_api import GitHubSnapshotPort
from .security import AdmissionError


@dataclass(frozen=True)
class PublicTrace:
    delivery_id: str
    event_type: str
    outcome: str
    check: str

    def as_public_dict(self) -> dict[str, str]:
        return asdict(self)


class WorkflowRouter:
    def __init__(self, github: GitHubSnapshotPort, executor: DesktopCommanderPort, capacity: int = 64):
        if not 1 <= capacity <= 1024:
            raise ValueError("capacity out of bounds")
        self.github = github
        self.executor = executor
        self.queue: asyncio.Queue[AdmittedEvent] = asyncio.Queue(maxsize=capacity)
        self.seen: set[str] = set()
        self.recent: deque[str] = deque()
        self.traces: list[PublicTrace] = []
        self._consumer: asyncio.Task[None] | None = None

    def submit(self, event: AdmittedEvent) -> str:
        if event.delivery_id in self.seen:
            return "DUPLICATE"
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull as exc:
            raise AdmissionError("QUEUE_FULL") from exc
        self.seen.add(event.delivery_id)
        self.recent.append(event.delivery_id)
        if len(self.recent) > 1024:
            self.seen.discard(self.recent.popleft())
        return "QUEUED"

    async def process_one(self) -> PublicTrace:
        event = await self.queue.get()
        try:
            snapshot = await self.github.get_commit(event.repository, event.commit_sha)
            if not snapshot.exists or snapshot.sha != event.commit_sha or snapshot.repository != event.repository:
                trace = PublicTrace(event.delivery_id, event.kind, "REVIEW", "SNAPSHOT_MISMATCH")
            else:
                outcome = await self.executor.run_approved("git_status")
                trace = PublicTrace(event.delivery_id, event.kind, outcome.status, "git_status")
        except AdmissionError as exc:
            trace = PublicTrace(event.delivery_id, event.kind, "BLOCKED", exc.code)
        except Exception:
            trace = PublicTrace(event.delivery_id, event.kind, "REVIEW", "ADAPTER_ERROR")
        finally:
            self.queue.task_done()
        self.traces.append(trace)
        if len(self.traces) > 100:
            self.traces.pop(0)
        return trace

    async def run_forever(self) -> None:
        while True:
            await self.process_one()

    def start(self) -> None:
        if self._consumer is None or self._consumer.done():
            self._consumer = asyncio.create_task(self.run_forever())

    async def stop(self) -> None:
        if self._consumer is not None:
            self._consumer.cancel()
            try:
                await self._consumer
            except asyncio.CancelledError:
                pass
            self._consumer = None
