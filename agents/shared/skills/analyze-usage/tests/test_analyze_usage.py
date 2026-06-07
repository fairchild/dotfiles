#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Regression tests for analyze-usage.

Usage:
  uv run skills/analyze-usage/tests/test_analyze_usage.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS: list[tuple[str, bool, str]] = []
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "analyze-usage"


def test(name: str):
    def decorator(fn):
        def wrapper() -> None:
            try:
                fn()
                TESTS.append((name, True, ""))
            except Exception as exc:  # pragma: no cover - harness output only
                TESTS.append((name, False, str(exc)))

        return wrapper

    return decorator


def run(cmd: list[str], *, env: dict[str, str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def duckdb_query(db_path: Path, sql: str) -> list[str]:
    result = subprocess.run(
        ["duckdb", "-csv", "-noheader", str(db_path), "-c", sql],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


def make_env(home: Path, db_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["ANALYZE_USAGE_DB"] = str(db_path)
    return env


def copy_standalone_script(target_dir: Path) -> Path:
    script_copy = target_dir / "analyze-usage"
    shutil.copy2(SCRIPT_PATH, script_copy)
    script_copy.chmod(0o755)
    return script_copy


def install_schema(home: Path) -> Path:
    schema_source = Path(__file__).resolve().parent.parent / "references" / "canonical-agent-schema.duckdb.sql"
    schema_target = home / ".local" / "share" / "analyze-usage" / "canonical-agent-schema.duckdb.sql"
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(schema_source, schema_target)
    return schema_target


def write_fixture(home: Path) -> Path:
    claude_dir = home / ".claude" / "projects" / "demo"
    claude_dir.mkdir(parents=True, exist_ok=True)
    session_file = claude_dir / "session.jsonl"
    cwd = "/Users/fairchild/conductor/workspaces/services/demo"
    entries = [
        {
            "uuid": "u1",
            "parentUuid": None,
            "sessionId": "s1",
            "type": "user",
            "timestamp": "2026-04-19T00:00:00Z",
            "cwd": cwd,
            "entrypoint": "cli",
            "isSidechain": False,
            "message": {"content": "hello"},
        },
        {
            "uuid": "a1",
            "parentUuid": "u1",
            "sessionId": "s1",
            "type": "assistant",
            "timestamp": "2026-04-19T00:00:01Z",
            "cwd": cwd,
            "entrypoint": "cli",
            "isSidechain": False,
            "message": {
                "model": "claude-sonnet-4-5-20250929",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
                "content": [
                    {"type": "text", "text": "hi"},
                    {"type": "tool_use", "name": "Bash", "input": {"command": "pwd"}},
                ],
            },
        },
        {
            "uuid": "sys1",
            "sessionId": "s1",
            "type": "system",
            "subtype": "turn_duration",
            "timestamp": "2026-04-19T00:00:02Z",
            "cwd": cwd,
            "gitBranch": "main",
            "durationMs": 123,
            "version": "1.0.0",
            "isSidechain": False,
        },
        {
            "sessionId": "s1",
            "type": "queue-operation",
            "timestamp": "2026-04-19T00:00:03Z",
            "operation": "enqueue",
            "content": "later",
        },
        {
            "sessionId": "s1",
            "type": "pr-link",
            "timestamp": "2026-04-19T00:00:04Z",
            "prNumber": 42,
            "prUrl": "https://example.com/pr/42",
            "prRepository": "fairchild/demo",
        },
    ]
    session_file.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    return session_file


def write_codex_fixture(home: Path) -> tuple[str, Path]:
    session_id = "019e6296-7f0f-7090-8572-a48ddfa5d34a"
    codex_home = home / ".codex"
    session_dir = codex_home / "sessions" / "2026" / "05" / "26"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / f"rollout-2026-05-26T00-00-00-{session_id}.jsonl"
    cwd = "/Users/fairchild/.worktrees/dotclaude/codex-import"
    entries = [
        {
            "timestamp": "2026-05-26T00:00:00.000Z",
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "timestamp": "2026-05-26T00:00:00.000Z",
                "cwd": cwd,
                "source": "cli",
                "originator": "codex_cli_rs",
                "cli_version": "1.0.0",
                "model_provider": "openai",
                "git": {
                    "branch": "feature/codex",
                    "commit_hash": "abc123",
                    "repository_url": "https://github.com/fairchild/dotclaude.git",
                },
            },
        },
        {
            "timestamp": "2026-05-26T00:00:01.000Z",
            "type": "turn_context",
            "payload": {
                "cwd": cwd,
                "model": "gpt-5-codex",
                "effort": "medium",
            },
        },
        {
            "timestamp": "2026-05-26T00:00:02.000Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": "developer policy"}],
            },
        },
        {
            "timestamp": "2026-05-26T00:00:03.000Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "show status"}],
            },
        },
        {
            "timestamp": "2026-05-26T00:00:04.000Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "arguments": json.dumps({"cmd": "pwd", "workdir": cwd}),
            },
        },
        {
            "timestamp": "2026-05-26T00:00:05.000Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "working tree clean"}],
            },
        },
        {
            "timestamp": "2026-05-26T00:00:06.000Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "last_token_usage": {
                        "input_tokens": 10,
                        "cached_input_tokens": 2,
                        "output_tokens": 5,
                        "reasoning_output_tokens": 1,
                        "total_tokens": 15,
                    },
                    "model_context_window": 258400,
                },
            },
        },
    ]
    session_file.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": session_id,
                "thread_name": "fixture thread",
                "updated_at": "2026-05-26T00:00:07.000Z",
            }
        )
        + "\n"
    )
    return session_id, session_file


def create_legacy_db(db_path: Path) -> None:
    sql = """
CREATE TABLE claude_tools (
    timestamp TIMESTAMP,
    session_id VARCHAR,
    project_dir VARCHAR,
    model VARCHAR,
    tool_name VARCHAR,
    context VARCHAR,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_write_tokens INTEGER,
    cache_read_tokens INTEGER,
    repo_name VARCHAR,
    worktree_branch VARCHAR,
    is_worktree BOOLEAN,
    source_file VARCHAR
);
CREATE TABLE messages (
    uuid VARCHAR,
    parent_uuid VARCHAR,
    session_id VARCHAR,
    role VARCHAR,
    harness VARCHAR,
    model VARCHAR,
    content VARCHAR,
    thinking VARCHAR,
    timestamp TIMESTAMP,
    project_dir VARCHAR,
    git_branch VARCHAR,
    repo_name VARCHAR,
    worktree_branch VARCHAR,
    is_worktree BOOLEAN,
    is_sidechain BOOLEAN,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_write_tokens INTEGER,
    cache_read_tokens INTEGER,
    tool_use_count INTEGER,
    source_file VARCHAR
);
CREATE TABLE _loaded_files (
    file_path VARCHAR PRIMARY KEY,
    mtime_ns BIGINT,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
    subprocess.run(["duckdb", str(db_path)], input=sql, text=True, check=True, timeout=30)


def assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(result.args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


@test("reload bootstraps canonical schema")
def test_reload_bootstraps_schema() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        session_file = write_fixture(home)
        db_path = Path(tmp) / "usage.duckdb"
        env = make_env(home, db_path)

        result = run([str(SCRIPT_PATH), "reload"], env=env)
        assert_ok(result)

        tables = duckdb_query(
            db_path,
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main' AND table_name LIKE 'agent_%' ORDER BY table_name;",
        )
        assert tables == [
            "agent_contexts",
            "agent_events",
            "agent_parts",
            "agent_raw_events",
            "agent_sessions",
            "agent_tokens",
            "agent_tool_calls",
            "agent_tool_results",
        ], tables

        interface_source = duckdb_query(
            db_path,
            "SELECT interface, source_file FROM claude_tools LIMIT 1;",
        )
        assert interface_source == [f"conductor,{session_file}"], interface_source

        message_rows = duckdb_query(
            db_path,
            "SELECT role, interface, tool_use_count FROM messages "
            "WHERE harness='claude_code' ORDER BY timestamp;",
        )
        assert message_rows == ["user,conductor,0", "assistant,conductor,1"], message_rows

        schema_output = run([str(SCRIPT_PATH), "--schema"], env=env)
        assert_ok(schema_output)
        assert "CANONICAL REFERENCE TABLES" in schema_output.stdout
        assert "agent_sessions" in schema_output.stdout
        assert "updated_at" in schema_output.stdout


@test("standalone installed script boots from installed schema file")
def test_standalone_script_bootstraps_schema() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        write_fixture(home)
        installed_schema = install_schema(home)
        db_path = Path(tmp) / "usage.duckdb"
        bin_dir = Path(tmp) / "bin"
        bin_dir.mkdir()
        standalone_script = copy_standalone_script(bin_dir)
        env = make_env(home, db_path)

        result = run([str(standalone_script), "reload"], env=env)
        assert_ok(result)

        tables = duckdb_query(
            db_path,
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main' AND table_name LIKE 'agent_%' ORDER BY table_name;",
        )
        assert tables == [
            "agent_contexts",
            "agent_events",
            "agent_parts",
            "agent_raw_events",
            "agent_sessions",
            "agent_tokens",
            "agent_tool_calls",
            "agent_tool_results",
        ], tables
        assert installed_schema.exists()


@test("reload imports Codex transcripts")
def test_reload_imports_codex_transcripts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        session_id, _session_file = write_codex_fixture(home)
        db_path = Path(tmp) / "usage.duckdb"
        env = make_env(home, db_path)

        result = run([str(SCRIPT_PATH), "reload"], env=env)
        assert_ok(result)

        codex_tools = duckdb_query(
            db_path,
            "SELECT tool_name, context, repo_name, worktree_branch FROM codex_tools;",
        )
        assert codex_tools == ["exec_command,pwd,dotclaude,codex-import"], codex_tools

        codex_messages = duckdb_query(
            db_path,
            "SELECT role, harness, interface, repo_name FROM messages "
            "WHERE harness='codex' ORDER BY role;",
        )
        assert codex_messages == [
            "assistant,codex,NULL,dotclaude",
            "user,codex,NULL,dotclaude",
        ], codex_messages

        codex_metadata = duckdb_query(
            db_path,
            "SELECT thread_name, git_branch, tool_count FROM codex_sessions;",
        )
        assert codex_metadata == ["fixture thread,feature/codex,1"], codex_metadata

        token_counts = duckdb_query(
            db_path,
            "SELECT input_tokens, cached_input_tokens, output_tokens, total_tokens "
            "FROM codex_token_counts;",
        )
        assert token_counts == ["10,2,5,15"], token_counts

        developer_messages = duckdb_query(
            db_path,
            "SELECT content FROM codex_developer_messages;",
        )
        assert developer_messages == ["developer policy"], developer_messages

        overview = duckdb_query(
            db_path,
            f"SELECT summary, git_branch FROM session_overview WHERE session_id='{session_id}';",
        )
        assert overview == ["fixture thread,feature/codex"], overview


@test("update imports Codex transcripts without Claude logs")
def test_update_imports_codex_without_claude_logs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        write_codex_fixture(home)
        db_path = Path(tmp) / "usage.duckdb"
        env = make_env(home, db_path)

        result = run([str(SCRIPT_PATH), "update"], env=env)
        assert_ok(result)
        assert "Binder Error" not in result.stderr, result.stderr

        codex_counts = duckdb_query(
            db_path,
            "SELECT COUNT(*), COUNT(DISTINCT session_id) FROM codex_tools;",
        )
        assert codex_counts == ["1,1"], codex_counts

        loaded_files = duckdb_query(
            db_path,
            "SELECT COUNT(*) FROM _loaded_files WHERE file_path LIKE '%.codex/%';",
        )
        assert loaded_files == ["2"], loaded_files


@test("update upgrades legacy table order safely")
def test_update_legacy_db_upgrade() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        session_file = write_fixture(home)
        db_path = Path(tmp) / "legacy.duckdb"
        create_legacy_db(db_path)
        env = make_env(home, db_path)

        result = run([str(SCRIPT_PATH), "update"], env=env)
        assert_ok(result)

        interface_source = duckdb_query(
            db_path,
            "SELECT interface, source_file FROM claude_tools LIMIT 1;",
        )
        assert interface_source == [f"conductor,{session_file}"], interface_source

        model_rows = duckdb_query(
            db_path,
            "SELECT interface, model, source_file FROM messages "
            "WHERE harness='claude_code' ORDER BY timestamp;",
        )
        assert model_rows == [
            f"conductor,NULL,{session_file}",
            f"conductor,claude-sonnet-4-5-20250929,{session_file}",
        ], model_rows

        canonical_count = duckdb_query(
            db_path,
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='main' AND table_name LIKE 'agent_%';",
        )
        assert canonical_count == ["8"], canonical_count


@test("update migrates legacy db even when tracked files are unchanged")
def test_update_legacy_db_no_change_migration() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        session_file = write_fixture(home)
        db_path = Path(tmp) / "legacy-current.duckdb"
        create_legacy_db(db_path)
        env = make_env(home, db_path)

        mtime_ns = session_file.stat().st_mtime_ns
        subprocess.run(
            [
                "duckdb",
                str(db_path),
                "-c",
                (
                    "INSERT INTO _loaded_files (file_path, mtime_ns) "
                    f"VALUES ('{session_file}', {mtime_ns});"
                ),
            ],
            text=True,
            check=True,
            timeout=30,
        )

        result = run([str(SCRIPT_PATH), "update"], env=env)
        assert_ok(result)

        columns = duckdb_query(
            db_path,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='claude_tools' ORDER BY ordinal_position;",
        )
        assert "interface" in columns, columns

        interface_source = duckdb_query(
            db_path,
            "SELECT interface, source_file FROM claude_tools LIMIT 1;",
        )
        assert interface_source == [f"conductor,{session_file}"], interface_source


def main() -> None:
    tests = [
        test_reload_bootstraps_schema,
        test_standalone_script_bootstraps_schema,
        test_reload_imports_codex_transcripts,
        test_update_imports_codex_without_claude_logs,
        test_update_legacy_db_upgrade,
        test_update_legacy_db_no_change_migration,
    ]
    for fn in tests:
        fn()

    passed = sum(1 for _, ok, _ in TESTS if ok)
    failed = sum(1 for _, ok, _ in TESTS if not ok)
    print(f"\n=== analyze-usage tests: {passed} passed, {failed} failed ===\n")
    for name, ok, err in TESTS:
        status = "PASS" if ok else "FAIL"
        line = f"  {status}  {name}"
        if err:
            line += f"  ({err})"
        print(line)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
