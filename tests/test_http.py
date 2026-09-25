"""HTTP tests exercise signature admission and queue behavior without outbound requests."""
import hashlib
import hmac
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from governed_agentic.executor import MockDesktopCommander
from governed_agentic.github_api import MockGitHubAPI
from governed_agentic.router import WorkflowRouter
from governed_agentic.webhook import create_app

REPO = 'example/workflow-demo'
EVENT = json.loads((Path(__file__).parents[1] / 'fixtures' / 'push.json').read_text())
DELIVERY = '11111111-2222-4333-8444-555555555555'


class WebhookHTTPTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GAB_WEBHOOK_SECRET': 'test-secret', 'GAB_REPOSITORY': REPO})
        self.env.start()
        self.router = WorkflowRouter(MockGitHubAPI(), MockDesktopCommander())
        self.client_ctx = TestClient(create_app(self.router))
        self.client = self.client_ctx.__enter__()

    def tearDown(self):
        self.client_ctx.__exit__(None, None, None)
        self.env.stop()

    def send(self, event=EVENT, *, delivery=DELIVERY, sign=True, kind='push'):
        body = json.dumps(event).encode()
        digest = hmac.new(b'test-secret', body, hashlib.sha256).hexdigest()
        return self.client.post('/webhook/github', content=body, headers={
            'x-github-delivery': delivery,
            'x-github-event': kind,
            'x-hub-signature-256': 'sha256=' + (digest if sign else '0' * 64),
            'content-type': 'application/json',
        })

    def test_signed_webhook_receipt(self):
        response = self.send()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {'receipt': 'QUEUED'})

    def test_bad_signature(self):
        response = self.send(sign=False)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['detail'], 'INVALID_SIGNATURE')

    def test_wrong_repository(self):
        response = self.send({**EVENT, 'repository': {'full_name': 'someone/other'}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['detail'], 'REPOSITORY_NOT_ALLOWED')

    def test_duplicate_receipt(self):
        self.assertEqual(self.send().status_code, 202)
        response = self.send()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'receipt': 'DUPLICATE'})

    def test_unsigned_json_rejected(self):
        response = self.client.post('/webhook/github', json=EVENT)
        self.assertEqual(response.status_code, 401)
