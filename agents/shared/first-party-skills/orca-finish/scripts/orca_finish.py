#!/usr/bin/env python3
"""Fail-closed readiness certification for a local Orca-managed worktree."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import urlsplit

SCHEMA = 3
FRESHNESS_SECONDS = 900
REMOTE_ENV_VARS = ("ORCA_ENVIRONMENT", "ORCA_PAIRING_CODE")


class Blocked(RuntimeError):
    pass


class OrcaError(Blocked):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise Blocked("evidence observed_at is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise Blocked("evidence observed_at must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def run(argv: list[str], cwd: Path | None = None, check: bool = True, timeout: int = 120, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        raise Blocked(f"command timed out after {timeout}s: {argv[0]}") from exc
    result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    if check and result.returncode:
        raise Blocked(f"command failed ({result.returncode}): {argv[0]}")
    return result


def git(cwd: Path, *args: str, check: bool = True) -> str:
    environment = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    return run(["git", *args], cwd=cwd, check=check, env=environment).stdout.strip()


def reject_remote_orca_environment() -> None:
    present = [name for name in REMOTE_ENV_VARS if os.environ.get(name)]
    if present:
        raise Blocked(f"remote Orca environments are unsupported; unset: {', '.join(present)}")


def orca(orca_bin: str, *args: str) -> tuple[Any, dict[str, Any]]:
    reject_remote_orca_environment()
    result = run([orca_bin, *args, "--json"], check=False, timeout=30)
    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise Blocked("Orca returned invalid JSON") from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("ok"), bool):
        raise Blocked("Orca returned an unknown response envelope")
    if not envelope["ok"] or result.returncode:
        error = envelope.get("error")
        code = error.get("code") if isinstance(error, dict) else "unknown_error"
        raise OrcaError(f"Orca command failed: {code}")
    meta = envelope.get("_meta")
    if not isinstance(meta, dict) or not meta.get("runtimeId"):
        raise Blocked("Orca response lacks local runtime identity")
    return envelope.get("result"), meta


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise Blocked("receipt directory must be an existing real directory")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise Blocked(f"cannot read valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise Blocked(f"expected JSON object: {path}")
    return payload


def load_json_bytes(content: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise Blocked(f"cannot parse valid JSON: {label}") from exc
    if not isinstance(payload, dict):
        raise Blocked(f"expected JSON object: {label}")
    return payload


def unwrap_worktree(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("worktree"), dict):
        return payload["worktree"]
    raise Blocked("Orca worktree response has an unknown shape")


def require_clean(path: Path, label: str) -> None:
    ordinary = [line for line in git(path, "status", "--porcelain=v1", "--untracked-files=all").splitlines() if line]
    ignored = [entry for entry in git(path, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").split("\0") if entry]
    if ordinary:
        raise Blocked(f"{label} has tracked or untracked changes")
    if ignored:
        raise Blocked(f"{label} has ignored files: {ignored[:5]}")


def assert_local_worktree(path: Path) -> None:
    if not path.is_absolute() or not path.exists() or git(path, "rev-parse", "--is-inside-work-tree") != "true":
        raise Blocked(f"not an existing local Git worktree: {path}")


def repo_identity(path: Path) -> dict[str, str]:
    common = Path(git(path, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (path / common).resolve()
    origin = git(path, "remote", "get-url", "origin")
    if "://" in origin:
        parsed = urlsplit(origin)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise Blocked("credential-bearing or parameterized origin URLs are unsupported")
    return {"common_dir": str(common), "origin_url": origin}


def default_branch(path: Path) -> str:
    ref = git(path, "symbolic-ref", "refs/remotes/origin/HEAD")
    prefix = "refs/remotes/origin/"
    if not ref.startswith(prefix):
        raise Blocked("origin/HEAD does not identify a default branch")
    return ref[len(prefix):]


def validate_adapter(adapter: dict[str, Any]) -> None:
    if adapter.get("schema_version") != SCHEMA or not adapter.get("name"):
        raise Blocked("missing or invalid repository adapter")
    completion = adapter.get("required_completion_checks")
    deletion = adapter.get("required_deletion_readiness_checks", [])
    deployment = adapter.get("deployment")
    if not isinstance(completion, list) or not completion or not all(isinstance(name, str) and name for name in completion):
        raise Blocked("adapter supplies no completion checks")
    if not isinstance(deletion, list) or not all(isinstance(name, str) and name for name in deletion) or not isinstance(deployment, dict) or not isinstance(deployment.get("required"), bool):
        raise Blocked("adapter deployment/deletion policy is invalid")
    if deployment["required"] and not deletion:
        raise Blocked("required deployment has no deletion-readiness check")


def validate_bound_evidence(payload: dict[str, Any], bindings: dict[str, str], label: str) -> None:
    if payload.get("schema_version") != SCHEMA:
        raise Blocked(f"{label} evidence schema is invalid")
    for key, expected in bindings.items():
        if payload.get(key) != expected:
            raise Blocked(f"{label} evidence binding mismatch: {key}")
    age = (dt.datetime.now(dt.timezone.utc) - parse_time(str(payload.get("observed_at", "")))).total_seconds()
    if age < -60 or age > FRESHNESS_SECONDS:
        raise Blocked(f"{label} evidence is stale or future-dated")


def validate_pr(payload: dict[str, Any], bindings: dict[str, str], canonical: Path) -> dict[str, Any]:
    required = ("provider", "repository", "pr", "base_branch", "state", "head_sha", "merge_sha", "required_checks", "review_decision", "unresolved_threads", "observed_at")
    if any(key not in payload for key in required):
        raise Blocked("PR evidence is missing required fields")
    validate_bound_evidence(payload, bindings, "PR")
    checks = payload["required_checks"]
    if not isinstance(payload["head_sha"], str) or not isinstance(payload["merge_sha"], str) or any(len(value) != 40 or any(character not in "0123456789abcdef" for character in value) for value in (payload["head_sha"], payload["merge_sha"])):
        raise Blocked("PR head and merge SHAs must be exact lowercase 40-hex values")
    if payload["state"] != "merged" or payload["review_decision"] not in {"approved", "not_required"} or payload["unresolved_threads"] != 0:
        raise Blocked("PR is not proven merged with acceptable review")
    if not isinstance(checks, list) or not checks or any(not isinstance(item, dict) or item.get("status") != "success" or not item.get("name") for item in checks):
        raise Blocked("named required checks are missing or not successful")
    if run(["git", "merge-base", "--is-ancestor", payload["merge_sha"], f"origin/{payload['base_branch']}"], cwd=canonical, check=False).returncode:
        raise Blocked("merge SHA is not contained by the remote default branch")
    sanitized = {key: payload[key] for key in required if key != "required_checks"}
    sanitized["required_checks"] = [{"name": item["name"], "status": "success"} for item in checks]
    return sanitized


def validate_check_evidence(payload: dict[str, Any], bindings: dict[str, str], required_names: list[str], label: str) -> list[dict[str, Any]]:
    validate_bound_evidence(payload, bindings, label)
    checks = payload.get("checks")
    if not isinstance(checks, list):
        raise Blocked(f"{label} evidence lacks checks")
    by_name = {item.get("name"): item for item in checks if isinstance(item, dict)}
    results = []
    for name in required_names:
        item = by_name.get(name)
        digest = item.get("command_sha256") if isinstance(item, dict) else None
        completed_at = item.get("completed_at") if isinstance(item, dict) else None
        if not isinstance(item, dict) or item.get("status") != "success" or not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise Blocked(f"required {label} check is missing or unsuccessful: {name}")
        completed_age = (dt.datetime.now(dt.timezone.utc) - parse_time(str(completed_at or ""))).total_seconds()
        if completed_age < -60 or completed_age > FRESHNESS_SECONDS:
            raise Blocked(f"required {label} check is stale: {name}")
        results.append({"name": name, "status": "success", "command_sha256": digest, "completed_at": completed_at})
    return results


def inspect(args: argparse.Namespace, prepare: bool) -> dict[str, Any]:
    target, canonical = Path(args.target).resolve(), Path(args.canonical_main).resolve()
    assert_local_worktree(target)
    assert_local_worktree(canonical)
    if target == canonical or repo_identity(target) != repo_identity(canonical):
        raise Blocked("target and canonical must be distinct worktrees of one repository")
    current_payload, meta = orca(args.orca, "worktree", "current")
    current = unwrap_worktree(current_payload)
    if Path(current.get("path", "")).resolve() != target or not current.get("id") or not current.get("instanceId"):
        raise Blocked("Orca current worktree does not exactly match target")
    require_clean(target, "target")
    require_clean(canonical, "canonical checkout")
    upstream = git(target, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if not upstream.startswith("origin/"):
        raise Blocked("only origin-backed worktrees are supported")
    if prepare:
        git(target, "fetch", "--prune", "origin")
        git(canonical, "fetch", "--prune", "origin")
    feature_head = git(target, "rev-parse", "HEAD")
    feature_branch = git(target, "symbolic-ref", "--short", "HEAD")
    if current.get("head") != feature_head or current.get("branch") not in {feature_branch, f"refs/heads/{feature_branch}"}:
        raise Blocked("Orca and Git head or branch disagree")
    if feature_head != git(target, "rev-parse", upstream):
        raise Blocked("feature HEAD is not exactly pushed to its upstream")
    main_branch = default_branch(canonical)
    canonical_head = git(canonical, "rev-parse", "HEAD")
    origin_head = git(canonical, "rev-parse", f"origin/{main_branch}")
    if git(canonical, "symbolic-ref", "--short", "HEAD") != main_branch or run(["git", "merge-base", "--is-ancestor", canonical_head, origin_head], cwd=canonical, check=False).returncode:
        raise Blocked("canonical checkout is not cleanly fast-forwardable on its default branch")
    repository = repo_identity(target)["origin_url"]
    bindings = {"repository": repository, "base_branch": main_branch, "head_sha": feature_head, "target_path": str(target), "orca_id": current["id"], "instance_id": current["instanceId"]}
    adapter_bytes = Path(args.adapter).read_bytes()
    adapter = load_json_bytes(adapter_bytes, str(args.adapter))
    validate_adapter(adapter)
    pr = validate_pr(load_json(Path(args.pr_evidence)), bindings, canonical)
    completion_checks = validate_check_evidence(load_json(Path(args.completion_evidence)), bindings, adapter["required_completion_checks"], "completion")
    deletion_checks = []
    if adapter["deployment"]["required"]:
        if not args.deployment_evidence:
            raise Blocked("deployment evidence is required")
        deletion_checks = validate_check_evidence(load_json(Path(args.deployment_evidence)), bindings, adapter["required_deletion_readiness_checks"], "deployment")
    if prepare:
        require_clean(target, "target after external checks")
        require_clean(canonical, "canonical checkout after external checks")
        if git(target, "rev-parse", "HEAD") != feature_head or git(canonical, "rev-parse", "HEAD") != canonical_head:
            raise Blocked("Git state drifted before certification")
    adapter_digest = hashlib.sha256(adapter_bytes).hexdigest()
    return {
        "schema_version": SCHEMA,
        "mode": "prepare" if prepare else "check",
        "observed_at": now(),
        "ready": True,
        "orca": {"runtime_id": meta["runtimeId"], "worktree_id": current["id"], "instance_id": current["instanceId"]},
        "target": {"path": str(target), "branch": feature_branch, "feature_head": feature_head, "upstream": upstream},
        "pr": pr,
        "canonical": {"path": str(canonical), "branch": main_branch, "head": canonical_head, "origin_head": origin_head},
        "adapter": {"name": adapter["name"], "sha256": adapter_digest, "completion_checks": completion_checks, "deletion_readiness_checks": deletion_checks, "deployment_required": adapter["deployment"]["required"]},
        "scope": "readiness-certification-only",
        "manual_action_required": True,
        "warnings": ["No resources were stopped or closed.", "No worktree or branch was removed.", "Current public Orca removal may delete the local feature branch."],
    }


def cmd_check(args: argparse.Namespace) -> int:
    try:
        report = inspect(args, prepare=False)
    except Blocked as exc:
        report = {"schema_version": SCHEMA, "mode": "check", "ready": False, "blocker": str(exc), "observed_at": now()}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 2


def cmd_prepare(args: argparse.Namespace) -> int:
    if args.authorize not in {"finish", "close", "remove"}:
        raise Blocked("prepare requires explicit closeout authorization")
    report = inspect(args, prepare=True)
    receipt_dir = Path(args.receipt_dir).expanduser().resolve()
    target = Path(args.target).resolve()
    canonical = Path(args.canonical_main).resolve()
    if receipt_dir == target or target in receipt_dir.parents or receipt_dir == canonical or canonical in receipt_dir.parents:
        raise Blocked("receipt directory must be outside target and canonical worktrees")
    if not receipt_dir.exists():
        receipt_dir.mkdir(parents=True, mode=0o700)
    if receipt_dir.is_symlink() or not receipt_dir.is_dir() or receipt_dir.stat().st_uid != os.getuid() or receipt_dir.stat().st_mode & 0o022:
        raise Blocked("receipt directory must be owner-controlled and not group/world writable")
    report["authorization"] = args.authorize
    receipt_id = hashlib.sha256(f"{report['orca']['worktree_id']}:{report['target']['feature_head']}:{report['observed_at']}".encode()).hexdigest()[:16]
    receipt_path = receipt_dir / f"orca-finish-{receipt_id}.json"
    atomic_json(receipt_path, report)
    print(json.dumps({"ready": True, "receipt": str(receipt_path), "scope": report["scope"], "manual_action_required": True, "warning": report["warnings"][-1]}, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("check", "prepare"):
        command = sub.add_parser(name)
        command.add_argument("--target", required=True)
        command.add_argument("--canonical-main", required=True)
        command.add_argument("--adapter", required=True)
        command.add_argument("--pr-evidence", required=True)
        command.add_argument("--completion-evidence", required=True)
        command.add_argument("--deployment-evidence")
        command.add_argument("--orca", default="orca")
        if name == "prepare":
            command.add_argument("--receipt-dir", required=True)
            command.add_argument("--authorize", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return {"check": cmd_check, "prepare": cmd_prepare}[args.command](args)
    except Blocked as exc:
        print(json.dumps({"ok": False, "state": "blocked", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
