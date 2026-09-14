"""Exercise the real release archive outside the source workspace."""

import io
import subprocess
import sys
import tarfile
import tempfile
import unittest

from tools.deploy_aws import bundle, template


class ReleaseTests(unittest.TestCase):
    def test_runtime_permission_is_bounded_to_upgrade_and_rollback_models(self):
        body = template("test-bucket", "release/test", "subnet-test", "vpc-test", "us-east-1a", "pl-test", "ami-test")
        statements = body["Resources"]["ServerRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        inference = [s for s in statements if s["Action"] == ["bedrock:InvokeModel"]]
        self.assertEqual(len(inference), 1)
        self.assertEqual(set(inference[0]["Resource"]), {
            "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0",
            "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0",
        })

    def test_release_starts_from_only_packaged_files(self):
        with tempfile.TemporaryDirectory() as directory:
            with tarfile.open(fileobj=io.BytesIO(bundle()), mode="r:gz") as archive:
                names = archive.getnames()
                self.assertIn("tools/acquire_fixture.py", names)
                self.assertFalse(any(name.startswith(("outputs/", ".env", ".aws/")) for name in names))
                archive.extractall(directory, filter="data")
            code = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from pantry_recall.web import Application
from pantry_recall.store import Store
from pantry_recall.fixtures import DEFAULT_FIXTURE
store = Store(Path(sys.argv[1]) / 'smoke.sqlite3')
store.initialize(DEFAULT_FIXTURE)
assert len(Application(store, None, 'https://demo.example').state()['cases']) == 8
print('Packaged application initialized all eight stock groups')
"""
            result = subprocess.run([sys.executable, "-I", "-c", code, directory], cwd=directory,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
