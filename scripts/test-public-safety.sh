#!/usr/bin/env bash
#MISE description="Exercise public-safety gates with positive and negative fixtures"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKER="$ROOT/scripts/check-public-safety.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
passed=0

make_repo() {
	local name="$1"
	REPO="$tmp/$name"
	mkdir -p "$REPO/agents/shared/third-party-patches" "$REPO/scripts"
	git -C "$REPO" init -q
	git -C "$REPO" config user.name fixture
	git -C "$REPO" config user.email fixture@example.com
	printf '# safe\n' > "$REPO/README.md"
	printf '# kind|path|content regex|reason\n' > "$REPO/scripts/public-safety-allowlist.txt"
	printf '{"version":1,"skills":{}}\n' > "$REPO/agents/shared/third-party-skills.lock.json"
	git -C "$REPO" add .
	git -C "$REPO" commit -qm baseline
}

expect_pass() {
	local name="$1"
	shift
	if "$@" >/dev/null 2>&1; then
		printf 'PASS: %s\n' "$name"
		passed=$((passed + 1))
	else
		printf 'FAIL: expected pass: %s\n' "$name" >&2
		exit 1
	fi
}

expect_fail() {
	local name="$1"
	shift
	if "$@" >/dev/null 2>&1; then
		printf 'FAIL: expected rejection: %s\n' "$name" >&2
		exit 1
	else
		printf 'PASS: rejected %s\n' "$name"
		passed=$((passed + 1))
	fi
}

make_repo baseline
expect_pass "safe baseline" "$CHECKER" --root "$REPO"

make_repo private-key-path
printf 'fixture\n' > "$REPO/id_ed25519"
git -C "$REPO" add -f id_ed25519
expect_fail "private key path" "$CHECKER" --root "$REPO"

make_repo private-key-content
printf '%s%s\n' '-----BEGIN ' 'PRIVATE KEY-----' >> "$REPO/README.md"
git -C "$REPO" add README.md
expect_fail "private key header" "$CHECKER" --root "$REPO"

make_repo credential-literal
printf 'token = "%s%s"\n' 'abcdefghijkl' 'mnop' >> "$REPO/README.md"
git -C "$REPO" add README.md
expect_fail "credential-shaped literal" "$CHECKER" --root "$REPO"

make_repo absolute-home
mkdir -p "$REPO/agents/shared/example"
printf '/Users/alice/private/path\n' > "$REPO/agents/shared/example/path.txt"
git -C "$REPO" add agents/shared/example/path.txt
expect_fail "absolute home path" "$CHECKER" --root "$REPO"
printf 'absolute-home|agents/shared/example/path.txt|/Users/alice/|synthetic fixture\n' >> "$REPO/scripts/public-safety-allowlist.txt"
git -C "$REPO" add scripts/public-safety-allowlist.txt
expect_pass "exact-path home allowlist" "$CHECKER" --root "$REPO"

make_repo runtime-jsonl
mkdir -p "$REPO/agents/shared/logs"
printf '{}\n' > "$REPO/agents/shared/logs/session.jsonl"
git -C "$REPO" add -f agents/shared/logs/session.jsonl
expect_fail "runtime JSONL" "$CHECKER" --root "$REPO"

make_repo materialized-skill
mkdir -p "$REPO/agents/shared/skills/vendor"
printf '# skill\n' > "$REPO/agents/shared/skills/vendor/SKILL.md"
git -C "$REPO" add agents/shared/skills/vendor/SKILL.md
expect_fail "materialized third-party skill" "$CHECKER" --root "$REPO"

make_repo incomplete-lock
printf '{"version":1,"skills":{"bad":{"source":"owner/repo"}}}\n' > "$REPO/agents/shared/third-party-skills.lock.json"
git -C "$REPO" add agents/shared/third-party-skills.lock.json
expect_fail "incomplete third-party provenance" "$CHECKER" --root "$REPO"

make_repo vendor-without-license
mkdir -p "$REPO/agents/shared/vendor/example"
printf 'third party\n' > "$REPO/agents/shared/vendor/example/file.txt"
git -C "$REPO" add agents/shared/vendor/example/file.txt
expect_fail "vendor without license" "$CHECKER" --root "$REPO"
printf 'license\n' > "$REPO/agents/shared/vendor/example/LICENSE"
printf 'Source: https://example.com/repo.git\nRevision: %040d\n' 0 > "$REPO/agents/shared/vendor/example/PROVENANCE.md"
git -C "$REPO" add agents/shared/vendor/example
expect_pass "vendor with provenance and license" "$CHECKER" --root "$REPO"

make_repo size-gate
base="$(git -C "$REPO" rev-parse HEAD)"
printf 'one\n' > "$REPO/one.txt"
printf 'two\n' > "$REPO/two.txt"
git -C "$REPO" add one.txt two.txt
git -C "$REPO" commit -qm large
expect_fail "oversized change" env PUBLIC_SAFETY_MAX_FILES=1 "$CHECKER" --root "$REPO" --base "$base" --head HEAD
expect_pass "explicit large-change override" env PUBLIC_SAFETY_MAX_FILES=1 PUBLIC_SAFETY_LARGE_PR_APPROVED=1 "$CHECKER" --root "$REPO" --base "$base" --head HEAD

if command -v gitleaks >/dev/null 2>&1; then
	mkdir -p "$tmp/gitleaks-safe" "$tmp/gitleaks-leak"
	printf 'gpg_key_fingerprint = "%040d"\n' 0 > "$tmp/gitleaks-safe/pin.toml"
	expect_pass "Gitleaks fingerprint allowlist" gitleaks dir --no-banner --redact --config "$ROOT/.gitleaks.toml" "$tmp/gitleaks-safe"
	printf 'github_token = "ghp_%s"\n' "$(openssl rand -hex 18)" > "$tmp/gitleaks-leak/secret.txt"
	expect_fail "Gitleaks secret fixture" gitleaks dir --no-banner --redact --config "$ROOT/.gitleaks.toml" "$tmp/gitleaks-leak"
else
	printf 'SKIP: Gitleaks fixture tests (binary not installed)\n'
fi

printf 'OK: %s public-safety fixture cases passed\n' "$passed"
