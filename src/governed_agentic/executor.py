"""Narrow, read-only OS execution seam. Nothing from webhook bodies becomes argv."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from .security import AdmissionError

MAX_CAPTURE = 4096
ALLOWED_COMMANDS: dict[str, tuple[str, ...]] = {
    "git_status": ("git", "status", "--short"),
    "git_head": ("git", "rev-parse", "HEAD"),
}


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    exit_code: int | None
    output_excerpt: str = ""


class DesktopCommanderPort(Protocol):
    async def run_approved(self, command_key: str) -> ExecutionResult: ...


class MockDesktopCommander:
    async def run_approved(self, command_key: str) -> ExecutionResult:
        if command_key not in ALLOWED_COMMANDS:
            raise AdmissionError("COMMAND_NOT_ALLOWED")
        return ExecutionResult("PASSED", 0, "synthetic mock response")


class LocalReadOnlyExecutor:
    """Opt-in local adapter. Use only with a trusted path, never a path from a webhook."""

    def __init__(self, workdir: Path, timeout_seconds: float = 5.0):
        self.workdir = workdir.resolve(strict=True)
        if not self.workdir.is_dir():
            raise ValueError("workdir must be a directory")
        if not 0 < timeout_seconds <= 30:
            raise ValueError("timeout out of bounds")
        self.timeout_seconds = timeout_seconds

    async def run_approved(self, command_key: str) -> ExecutionResult:
        argv = ALLOWED_COMMANDS.get(command_key)
        if argv is None:
            raise AdmissionError("COMMAND_NOT_ALLOWED")
        process = await asyncio.create_subprocess_exec(
            *argv, cwd=self.workdir,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), self.timeout_seconds)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return ExecutionResult("TIMED_OUT", None)
        status = "PASSED" if process.returncode == 0 else "FAILED"
        return ExecutionResult(status, process.returncode, stdout[:MAX_CAPTURE].decode("utf-8", "replace"))
