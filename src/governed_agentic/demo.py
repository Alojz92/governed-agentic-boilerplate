"""Offline end-to-end demonstration; fixture is synthetic."""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from .events import admit_event
from .executor import MockDesktopCommander
from .github_api import MockGitHubAPI
from .job_spec import match_requirements
from .router import WorkflowRouter


async def main() -> None:
    file = Path(__file__).parents[2] / "fixtures" / "push.json"
    payload = json.loads(file.read_text(encoding="utf-8"))
    router = WorkflowRouter(MockGitHubAPI(), MockDesktopCommander())
    event = admit_event(payload, "push", "11111111-2222-4333-8444-555555555555", "example/workflow-demo")
    print("receipt:", router.submit(event))
    print("public trace:", json.dumps((await router.process_one()).as_public_dict(), sort_keys=True))
    example = json.loads((file.parent / "job-requirements.json").read_text(encoding="utf-8"))
    rows = match_requirements(example["requirements"], example["approved_public_capabilities"])
    print("synthetic job-spec comparison:", json.dumps(rows, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
