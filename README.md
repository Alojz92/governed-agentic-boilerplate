# Governed Agentic Boilerplate

A small, **standalone reference implementation** of GitHub webhook intake, asynchronous event routing, bounded local execution, and deterministic validation at the LLM-to-tool boundary. It is newly written sample code, **not an export, SDK, or copy of any private Software Factory or Desktop Commander implementation**.

## What it demonstrates

`GitHub webhook -> HMAC verification -> constrained event parser -> bounded async queue -> repository snapshot -> approved read-only command -> sanitized trace`

- Python 3.11+, asyncio and FastAPI as a thin HTTP adapter.
- HMAC-SHA256 webhook signature checked over the original request bytes, before JSON interpretation.
- Exact repository, event type, branch, action and 40-character commit SHA validation. Untrusted webhook content is data, never an instruction or a shell command.
- A mock GitHub API client, an optional read-only GitHub REST adapter, and a mock Desktop Commander-style execution adapter for offline demonstration. The optional local subprocess adapter executes only predeclared argument vectors inside a chosen work directory: no arbitrary tool calls, shell commands, checkout or GitHub writes.
- Queue backpressure, bounded command duration, output-size caps, explicit outcome classes and best-effort webhook delivery deduplication **in this process only**.
- A reproducible synthetic trace, and tests for rejected signatures, repository confusion, unsupported events, injection attempts and timeouts.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[server,test]"
python -m unittest discover -s tests -v
python -m governed_agentic.demo
```

The demo prints one synthetic GitHub-event trace and an example job-spec comparison with `SUPPORTED`, `GAP` and `UNKNOWN` rows. The comparator accepts already-extracted atomic requirements; it does not fetch job URLs, infer requirements from arbitrary prose, or access the private candidate evidence system.

To run the optional HTTP endpoint:

```bash
export GAB_WEBHOOK_SECRET='a locally generated test-only secret'
export GAB_REPOSITORY='example/workflow-demo'
uvicorn governed_agentic.webhook:app --host 127.0.0.1 --port 8080
```

For a real deployment, create a new secret in a secret manager; do not use the example value, commit it or paste it into logs. The HTTP demo uses mock GitHub and mock execution by default. `GitHubReadOnlyAPI(expected_repository, token)` is an optional read-only commit-snapshot seam, not wired to public HTTP by default. The HTTP adapter returns HTTP 503 when the secret is absent; public ingress additionally requires TLS, ingress limits, authentication/authorization for operational endpoints and durable queue storage.

## Architecture decisions

| Boundary | Design | Failure behavior |
|---|---|---|
| Webhook ingress | Verify `X-Hub-Signature-256`; check content length and unique delivery ID | 400 / 401 / 413 / 422 |
| Event admission | Allow only `push` on `refs/heads/main` and `pull_request` on opened/synchronize; reject unexpected owners/repositories/SHAs | Reject and record reason code |
| Event queue | Bounded `asyncio.Queue`, one demonstration consumer; in-memory delivery dedupe | 503 when capacity exhausted; no false acceptance |
| Repository data | Exact expected repository; mock API returns deterministic snapshot | Missing/mismatched SHA -> REVIEW |
| Execution | An adapter Protocol separates execution from event analysis; subprocess adapter accepts a predeclared command key | Unknown command -> BLOCKED; timeout -> TIMED_OUT |
| Trace | Fixed public fields, synthetic IDs, no payload echo or stdout/stderr logging by default | Minimal outcome-only record |
| LLM | No model is required in the demo. If added, suggestions become untrusted candidates for deterministic validation | Unsupported proposal -> BLOCKED |

### Why the bridge is mock-only

The `DesktopCommanderPort` interface is a demonstration of the architectural seam between orchestration and an authorized host executor. It is not a Desktop Commander connection, not a remote machine bridge and not an endorsement of a vendor interface. Any real connector must introduce its own identity, scoped consent, workstation isolation and host-side authorization. This public sample intentionally provides **no network endpoint** that can run arbitrary operating-system commands.

### Handling hallucinations

The defensible claim is **reducing unsupported actions and unsupported output**, not eliminating hallucinations. An LLM may propose an event label, repo ref, command key or explanation, but deterministic rules validate the proposal against explicit configuration and source data before effects. The tests verify individual boundaries, not total LLM factual accuracy.

### Limitations

This is a teaching artifact, not an external-client production deployment, an extraction of proprietary algorithms, or evidence of cost savings/conversion uplift. Dedupe and queue state are in-memory and non-durable; the HTTP adapter does not verify that a webhook sender controls the repository beyond its shared signing secret; retries, durable idempotency, isolation, deployment hardening, GitHub App token lifecycle and independent review require separate production design. Never accept an arbitrary repo, script or target directory from event payloads.

## Public disclosure checklist

Read `PUBLICATION_CHECKLIST.md` and `docs/TERMINOLOGY_AND_MODEL_CONTEXT.md` before publishing. All fixture names and events are synthetic. Do not replace mocks with private provider URLs, credentials, repository graphs, cost telemetry, customer information, live execution logs or proprietary prompts.

## License

MIT, applying only to the newly authored contents of this reference repository. No private code or rights are conveyed.
