#!/usr/bin/env python3
"""Disposable tests for readiness-only orca_finish.py."""

import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("orca_finish.py")


def run(argv, cwd=None, env=None, ok=True):
    result = subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True)
    if ok and result.returncode:
        raise AssertionError(f"{argv}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result


class FinishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orca-finish-test-"))
        self.remote, self.main, self.target = self.tmp / "remote.git", self.tmp / "main", self.tmp / "feature"
        run(["git", "init", "--bare", str(self.remote)])
        run(["git", "clone", str(self.remote), str(self.main)])
        run(["git", "config", "user.email", "test@example.invalid"], self.main)
        run(["git", "config", "user.name", "Test"], self.main)
        (self.main / ".gitignore").write_text("ignored\n")
        (self.main / "base").write_text("base\n")
        run(["git", "add", "."], self.main); run(["git", "commit", "-m", "base"], self.main)
        run(["git", "branch", "-M", "main"], self.main); run(["git", "push", "-u", "origin", "main"], self.main)
        run(["git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main"]); run(["git", "remote", "set-head", "origin", "-a"], self.main)
        run(["git", "worktree", "add", "-b", "feature", str(self.target), "main"], self.main)
        (self.target / "feature").write_text("feature\n")
        run(["git", "add", "feature"], self.target); run(["git", "commit", "-m", "feature"], self.target); run(["git", "push", "-u", "origin", "feature"], self.target)
        self.feature = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip()
        run(["git", "merge", "--ff-only", "feature"], self.main); run(["git", "push", "origin", "main"], self.main)
        self.merge = run(["git", "rev-parse", "HEAD"], self.main).stdout.strip()
        self.state = self.tmp / "orca-state.json"; self.fake = self.tmp / "orca"
        self.state.write_text(json.dumps({"path": str(self.target), "head": self.feature, "calls": []}))
        self.fake.write_text(FAKE_ORCA); self.fake.chmod(0o755)
        self.write_evidence()
        self.write_completion_evidence()
        self.adapter = self.tmp / "adapter.json"
        self.adapter.write_text(json.dumps({"schema_version": 3, "name": "fixture", "required_completion_checks": ["base"], "required_deletion_readiness_checks": [], "deployment": {"required": False}}))

    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def observed(self): return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    def env(self, **extra): return {**os.environ, "FAKE_ORCA_STATE": str(self.state), **extra}

    def write_evidence(self, **changes):
        payload = {"schema_version": 3, "provider": "fake", "repository": str(self.remote), "pr": "#1", "base_branch": "main", "state": "merged", "head_sha": self.feature, "merge_sha": self.merge, "required_checks": [{"name": "test", "status": "success"}], "review_decision": "approved", "unresolved_threads": 0, "observed_at": self.observed(), "target_path": str(self.target.resolve()), "orca_id": "repo::" + str(self.target), "instance_id": "instance-fixture"}
        payload.update(changes)
        self.evidence = self.tmp / "pr.json"; self.evidence.write_text(json.dumps(payload))

    def write_completion_evidence(self, **changes):
        payload = {"schema_version": 3, "repository": str(self.remote), "base_branch": "main", "head_sha": self.feature, "target_path": str(self.target.resolve()), "orca_id": "repo::" + str(self.target), "instance_id": "instance-fixture", "observed_at": self.observed(), "checks": [{"name": "base", "status": "success", "command_sha256": "a" * 64, "completed_at": self.observed()}]}
        payload.update(changes)
        self.completion = self.tmp / "completion.json"; self.completion.write_text(json.dumps(payload))

    def args(self, mode): return [str(SCRIPT), mode, "--target", str(self.target), "--canonical-main", str(self.main), "--adapter", str(self.adapter), "--pr-evidence", str(self.evidence), "--completion-evidence", str(self.completion), "--orca", str(self.fake)]

    def test_check_is_read_only(self):
        result = run(self.args("check"), env=self.env()); self.assertTrue(json.loads(result.stdout)["ready"])
        calls = json.loads(self.state.read_text())["calls"]
        self.assertEqual([call[:2] for call in calls], [["worktree", "current"]])

    def test_prepare_writes_certification_without_removal(self):
        result = run(self.args("prepare") + ["--receipt-dir", str(self.tmp / "receipts"), "--authorize", "finish"], env=self.env())
        output = json.loads(result.stdout); receipt = json.loads(Path(output["receipt"]).read_text())
        self.assertEqual(receipt["scope"], "readiness-certification-only")
        self.assertTrue(receipt["manual_action_required"]); self.assertTrue(self.target.exists())
        calls = json.loads(self.state.read_text())["calls"]
        self.assertNotIn(["worktree", "rm"], [call[:2] for call in calls])
        self.assertFalse(any(call and call[0] in {"terminal", "tab", "emulator"} for call in calls))

    def test_ignored_and_untracked_files_block(self):
        (self.target / "ignored").write_text("private\n")
        self.assertIn("ignored files", run(self.args("check"), env=self.env(), ok=False).stdout)
        (self.target / "ignored").unlink(); (self.target / "untracked").write_text("mine\n")
        self.assertIn("tracked or untracked", run(self.args("check"), env=self.env(), ok=False).stdout)

    def test_ambiguous_authorization_and_remote_environment_block(self):
        result = run(self.args("prepare") + ["--receipt-dir", str(self.tmp / "receipts"), "--authorize", "archive"], env=self.env(), ok=False)
        self.assertEqual(result.returncode, 2); self.assertNotIn("Traceback", result.stderr)
        self.assertIn("explicit closeout authorization", json.loads(result.stderr)["error"])
        self.assertIn("remote Orca", run(self.args("check"), env=self.env(ORCA_ENVIRONMENT="remote"), ok=False).stdout)

    def test_stale_evidence_and_unpushed_head_block(self):
        self.write_evidence(observed_at="2020-01-01T00:00:00Z")
        self.assertIn("stale", run(self.args("check"), env=self.env(), ok=False).stdout)
        self.write_evidence(); (self.target / "later").write_text("later\n"); run(["git", "add", "later"], self.target); run(["git", "commit", "-m", "unpushed"], self.target)
        state = json.loads(self.state.read_text()); state["head"] = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip(); self.state.write_text(json.dumps(state))
        self.assertIn("not exactly pushed", run(self.args("check"), env=self.env(), ok=False).stdout)

    def test_receipt_cannot_live_in_a_worktree(self):
        result = run(self.args("prepare") + ["--receipt-dir", str(self.main / "receipts"), "--authorize", "finish"], env=self.env(), ok=False)
        self.assertIn("outside target and canonical", result.stderr)

    def test_world_writable_receipt_directory_blocks(self):
        receipts = self.tmp / "receipts"; receipts.mkdir(); receipts.chmod(0o777)
        result = run(self.args("prepare") + ["--receipt-dir", str(receipts), "--authorize", "finish"], env=self.env(), ok=False)
        self.assertIn("owner-controlled", result.stderr)

    def test_orca_git_binding_mismatch_blocks(self):
        state = json.loads(self.state.read_text()); state["head"] = "0" * 40; self.state.write_text(json.dumps(state))
        self.assertIn("Orca and Git", run(self.args("check"), env=self.env(), ok=False).stdout)

    def test_symbolic_merge_sha_and_stale_check_block(self):
        self.write_evidence(merge_sha="origin/main")
        self.assertIn("exact lowercase 40-hex", run(self.args("check"), env=self.env(), ok=False).stdout)
        self.write_evidence(); self.write_completion_evidence()
        payload = json.loads(self.completion.read_text()); payload["checks"][0]["completed_at"] = "2020-01-01T00:00:00Z"; self.completion.write_text(json.dumps(payload))
        self.assertIn("check is stale", run(self.args("check"), env=self.env(), ok=False).stdout)

    def test_pr_extra_fields_are_not_retained(self):
        self.write_evidence(required_checks=[{"name": "test", "status": "success", "output": "private-payload"}])
        report = json.loads(run(self.args("check"), env=self.env()).stdout)
        self.assertNotIn("output", report["pr"]["required_checks"][0])

    def test_parameterized_origin_url_blocks(self):
        origin = "https://example.invalid/repo.git?access_token=synthetic-placeholder"
        run(["git", "remote", "set-url", "origin", origin], self.main)
        self.write_evidence(repository=origin); self.write_completion_evidence(repository=origin)
        self.assertIn("parameterized origin", run(self.args("check"), env=self.env(), ok=False).stdout)


FAKE_ORCA = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
p=pathlib.Path(os.environ["FAKE_ORCA_STATE"]); s=json.loads(p.read_text()); a=[v for v in sys.argv[1:] if v!="--json"]; s["calls"].append(a); p.write_text(json.dumps(s))
def emit(result): print(json.dumps({"ok":True,"result":result,"_meta":{"runtimeId":"runtime-fixture"}})); raise SystemExit
wt={"id":"repo::"+s["path"],"instanceId":"instance-fixture","path":s["path"],"head":s["head"],"branch":"refs/heads/feature"}
if a[:2]==["worktree","current"]: emit({"worktree":wt})
print(json.dumps({"ok":False,"error":{"code":"unexpected"},"_meta":{"runtimeId":"runtime-fixture"}})); raise SystemExit(1)
'''


if __name__ == "__main__": unittest.main()
