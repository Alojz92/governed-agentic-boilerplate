"""HTTP adapter for synthetic webhook-based workflow tests."""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from .events import admit_event
from .executor import MockDesktopCommander
from .github_api import MockGitHubAPI
from .router import WorkflowRouter
from .security import AdmissionError, verify_delivery_id, verify_webhook, MAX_BODY_BYTES


def create_app(router: WorkflowRouter | None = None) -> FastAPI:
    secret = os.getenv("GAB_WEBHOOK_SECRET", "")
    expected_repo = os.getenv("GAB_REPOSITORY", "example/workflow-demo")
    router = router or WorkflowRouter(MockGitHubAPI(repository=expected_repo), MockDesktopCommander())

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        router.start()
        yield
        await router.stop()

    api = FastAPI(title="Governed Agentic Boilerplate", lifespan=lifespan, docs_url=None, redoc_url=None)

    @api.post("/webhook/github")
    async def github_webhook(request: Request):
        if request.headers.get("content-length", "").isdigit() and int(request.headers["content-length"]) > MAX_BODY_BYTES:
            raise HTTPException(413, "PAYLOAD_TOO_LARGE")
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(413, "PAYLOAD_TOO_LARGE")
        try:
            verify_webhook(body, request.headers.get("x-hub-signature-256"), secret)
            delivery_id = verify_delivery_id(request.headers.get("x-github-delivery"))
            payload = json.loads(body)
            event = admit_event(payload, request.headers.get("x-github-event", ""), delivery_id, expected_repo)
            receipt = router.submit(event)
        except AdmissionError as exc:
            code = exc.code
            status = 503 if code in {"WEBHOOK_SECRET_UNAVAILABLE", "QUEUE_FULL"} else 401 if code == "INVALID_SIGNATURE" else 422
            raise HTTPException(status, code) from exc
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(400, "INVALID_JSON") from exc
        return JSONResponse({"receipt": receipt}, status_code=202 if receipt == "QUEUED" else 200)

    return api


app = create_app()
