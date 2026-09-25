import asyncio
import hashlib
import hmac
import json
from pathlib import Path
import unittest

from governed_agentic.security import AdmissionError, verify_webhook, verify_delivery_id
from governed_agentic.events import admit_event
from governed_agentic.executor import MockDesktopCommander, LocalReadOnlyExecutor
from governed_agentic.github_api import MockGitHubAPI
from governed_agentic.router import WorkflowRouter

PAYLOAD = json.loads((Path(__file__).parents[1] / 'fixtures' / 'push.json').read_text())
DELIVERY = '11111111-2222-4333-8444-555555555555'
REPO = 'example/workflow-demo'


class AdmissionTests(unittest.TestCase):
    def test_valid_signature(self):
        body = json.dumps(PAYLOAD).encode()
        digest = hmac.new(b'test-secret', body, hashlib.sha256).hexdigest()
        verify_webhook(body, 'sha256=' + digest, 'test-secret')

    def test_bad_signature(self):
        with self.assertRaisesRegex(AdmissionError, 'INVALID_SIGNATURE'):
            verify_webhook(b'{}', 'sha256=' + '0' * 64, 'test-secret')

    def test_missing_secret(self):
        with self.assertRaisesRegex(AdmissionError, 'WEBHOOK_SECRET_UNAVAILABLE'):
            verify_webhook(b'{}', 'sha256=' + '0' * 64, '')

    def test_invalid_delivery(self):
        with self.assertRaisesRegex(AdmissionError, 'INVALID_DELIVERY_ID'):
            verify_delivery_id('../../../secrets')

    def test_exact_repository(self):
        hostile = {**PAYLOAD, 'repository': {'full_name': 'example/other'}}
        with self.assertRaisesRegex(AdmissionError, 'REPOSITORY_NOT_ALLOWED'):
            admit_event(hostile, 'push', DELIVERY, REPO)

    def test_reject_untrusted_branch_and_sha(self):
        for payload in ({**PAYLOAD, 'ref': 'refs/heads/other'},
                        {**PAYLOAD, 'after': '$(curl attacker)'},
                        {**PAYLOAD, 'deleted': True}):
            with self.subTest(payload=payload), self.assertRaises(AdmissionError):
                admit_event(payload, 'push', DELIVERY, REPO)

    def test_reject_unknown_event_and_fork(self):
        with self.assertRaisesRegex(AdmissionError, 'UNSUPPORTED_EVENT'):
            admit_event(PAYLOAD, 'repository_dispatch', DELIVERY, REPO)
        pr = {'repository': {'full_name': REPO}, 'action': 'opened',
              'pull_request': {'head': {'sha': 'a' * 40, 'repo': {'full_name': 'other/fork'}}}}
        with self.assertRaisesRegex(AdmissionError, 'FORK_NOT_ALLOWED'):
            admit_event(pr, 'pull_request', DELIVERY, REPO)


class RouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_end_to_end_with_mock(self):
        event = admit_event(PAYLOAD, 'push', DELIVERY, REPO)
        router = WorkflowRouter(MockGitHubAPI(), MockDesktopCommander())
        self.assertEqual(router.submit(event), 'QUEUED')
        self.assertEqual(router.submit(event), 'DUPLICATE')
        trace = await router.process_one()
        self.assertEqual(trace.outcome, 'PASSED')
        self.assertEqual(set(trace.as_public_dict()), {'delivery_id', 'event_type', 'outcome', 'check'})

    async def test_unknown_command_rejected(self):
        with self.assertRaisesRegex(AdmissionError, 'COMMAND_NOT_ALLOWED'):
            await MockDesktopCommander().run_approved('rm_everything')

    async def test_snapshot_mismatch_blocks(self):
        router = WorkflowRouter(MockGitHubAPI(sha='b' * 40), MockDesktopCommander())
        router.submit(admit_event(PAYLOAD, 'push', DELIVERY, REPO))
        self.assertEqual((await router.process_one()).outcome, 'BLOCKED')

    async def test_queue_backpressure(self):
        router = WorkflowRouter(MockGitHubAPI(), MockDesktopCommander(), capacity=1)
        router.submit(admit_event(PAYLOAD, 'push', DELIVERY, REPO))
        with self.assertRaisesRegex(AdmissionError, 'QUEUE_FULL'):
            router.submit(admit_event(PAYLOAD, 'push', '22222222-2222-4333-8444-555555555555', REPO))

    async def test_local_executor_never_accepts_arbitrary_argv(self):
        runner = LocalReadOnlyExecutor(Path(__file__).parents[1])
        with self.assertRaisesRegex(AdmissionError, 'COMMAND_NOT_ALLOWED'):
            await runner.run_approved('git status; printenv')

    async def test_timeout_result(self):
        class SlowMock:
            async def get_commit(self, repo, sha):
                await asyncio.sleep(0)
                return type('Snapshot', (), {'repository': repo, 'sha': sha, 'exists': True})()
        class SlowExecutor:
            async def run_approved(self, key):
                raise TimeoutError()
        router = WorkflowRouter(SlowMock(), SlowExecutor())
        router.submit(admit_event(PAYLOAD, 'push', DELIVERY, REPO))
        self.assertEqual((await router.process_one()).outcome, 'REVIEW')

class JobSpecTests(unittest.TestCase):
    def test_no_promoting_unknown_as_supported(self):
        from governed_agentic.job_spec import match_requirements
        rows = match_requirements([{'id': 'A', 'text': 'test', 'capability': 'x'}],
                                  {'x': {'status': 'SUPPORTED', 'evidence_refs': []}})
        self.assertEqual(rows[0]['status'], 'UNKNOWN')

    def test_demo_with_explicit_gap(self):
        from governed_agentic.job_spec import match_requirements
        p = json.loads((Path(__file__).parents[1] / 'fixtures' / 'job-requirements.json').read_text())
        rows = match_requirements(p['requirements'], p['approved_public_capabilities'])
        self.assertEqual([x['status'] for x in rows], ['SUPPORTED', 'GAP', 'UNKNOWN'])

class GitHubAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_adapter_refuses_foreign_repo_without_network(self):
        from governed_agentic.github_api import GitHubReadOnlyAPI
        adapter = GitHubReadOnlyAPI(REPO, 'FAKE_TEST_TOKEN_DO_NOT_USE')
        with self.assertRaisesRegex(AdmissionError, 'SNAPSHOT_REQUEST_NOT_ALLOWED'):
            await adapter.get_commit('other/repo', 'a' * 40)
