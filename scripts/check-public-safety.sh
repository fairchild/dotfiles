#!/usr/bin/env bash
#MISE description="Reject secrets, private runtime, and unmanaged third-party material"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE=""
HEAD="HEAD"

while [[ $# -gt 0 ]]; do
	case "$1" in
		--root) ROOT="$(cd "$2" && pwd)"; shift 2 ;;
		--base) BASE="$2"; shift 2 ;;
		--head) HEAD="$2"; shift 2 ;;
		*) echo "usage: $0 [--root PATH] [--base REF --head REF]" >&2; exit 2 ;;
	esac
done

ALLOWLIST="${DOTFILES_SAFETY_ALLOWLIST:-$ROOT/scripts/public-safety-allowlist.txt}"
MAX_FILES="${PUBLIC_SAFETY_MAX_FILES:-150}"
MAX_ADDED="${PUBLIC_SAFETY_MAX_ADDED_LINES:-20000}"
MAX_CHANGED="${PUBLIC_SAFETY_MAX_CHANGED_LINES:-30000}"
APPROVED_LARGE="${PUBLIC_SAFETY_LARGE_PR_APPROVED:-0}"
failures=0

for command_name in git jq awk grep; do
	command -v "$command_name" >/dev/null 2>&1 \
		|| { echo "FAIL: required command not found: $command_name" >&2; exit 1; }
done

[[ -f "$ALLOWLIST" ]] || { echo "FAIL: safety allowlist missing: $ALLOWLIST" >&2; exit 1; }

is_allowed() {
	local kind="$1" path="$2" detail="$3"
	awk -F'|' -v kind="$kind" -v path="$path" -v detail="$detail" '
		$0 !~ /^#/ && $1 == kind && $2 == path && detail ~ $3 { found = 1 }
		END { exit(found ? 0 : 1) }
	' "$ALLOWLIST"
}

report() {
	local kind="$1" path="$2" detail="$3" evidence="${4:-$3}"
	if is_allowed "$kind" "$path" "$evidence"; then
		printf 'ALLOW: %s: %s (%s)\n' "$kind" "$path" "$detail"
		return
	fi
	printf 'FAIL: %s: %s (%s)\n' "$kind" "$path" "$detail" >&2
	failures=$((failures + 1))
}

while IFS= read -r line; do
	[[ -z "$line" || "$line" == \#* ]] && continue
	if [[ "$(awk -F'|' '{print NF}' <<< "$line")" -lt 4 ]]; then
		echo "FAIL: malformed allowlist entry: $line" >&2
		exit 1
	fi
	allowed_path="$(awk -F'|' '{print $2}' <<< "$line")"
	git -C "$ROOT" ls-files --error-unmatch "$allowed_path" >/dev/null 2>&1 \
		|| { echo "FAIL: allowlist path is not tracked: $allowed_path" >&2; exit 1; }
done < "$ALLOWLIST"

while IFS= read -r path; do
	base="${path##*/}"
	case "$path" in
		*.pem|*.key|*.p12|*.pfx|*.kdbx|id_rsa|id_ed25519|id_ecdsa|*/id_rsa|*/id_ed25519|*/id_ecdsa|.env|*/.env)
			report private-key-path "$path" "credential or private-key filename"
			;;
	esac

	case "$base" in
		HANDOFF.md|handoff.md|TODO.md|todo.md|todo.txt|*.jsonl|*.log|.DS_Store|installed_plugins.json|known_marketplaces.json|plugin-cache.json)
			report runtime-artifact "$path" "runtime or internal-work artifact"
			;;
	esac

	case "$path" in
		*/runtime-backups/*|*/outputs/*|*/output/*|*/logs/*|*/cache/*|*/.cache/*|*/tmp/*|*/generated/*)
			case "$base" in
				README.md|.gitignore|.gitkeep) ;;
				*) report runtime-artifact "$path" "generated/runtime directory" ;;
			esac
			;;
	esac

	case "$path" in
		agents/shared/skills/*)
			report third-party-runtime "$path" "lock-managed runtime must not be tracked"
			;;
	esac
done < <(git -C "$ROOT" ls-files)

while IFS= read -r match; do
	path="${match%%:*}"
	rest="${match#*:}"
	line="${rest%%:*}"
	report private-key-content "$path" "private-key header at line $line" "$match"
done < <(git -C "$ROOT" grep -I -n -E -e '-----BEGIN ([A-Z0-9 ]+ )?PRIVATE KEY-----' -- . 2>/dev/null || true)

quoted_secret_re="(api[_-]?key|secret|token|password|passwd|client[_-]?secret|access[_-]?key)[[:alnum:]_-]*[[:space:]]*[:=][[:space:]]*[\"'][A-Za-z0-9_+./=-]{8,}[\"']"
shell_secret_re='(API_KEY|SECRET|TOKEN|PASSWORD|PASSWD|CLIENT_SECRET|ACCESS_KEY)[A-Z0-9_]*[[:space:]]*=[[:space:]]*[A-Za-z0-9_+/=-]{12,}([[:space:]]|$)'
while IFS= read -r match; do
	path="${match%%:*}"
	content="${match#*:}"
	if grep -Eqi 'your-key-here|example|change[-_]?me|redacted|placeholder|keep-listening|stop-listening|boundary=|\.\.\.' <<< "$content"; then
		continue
	fi
	line="${content%%:*}"
	report credential-literal "$path" "credential-shaped literal at line $line" "$match"
done < <(git -C "$ROOT" grep -I -n -E -i -e "$quoted_secret_re" -e "$shell_secret_re" -- . 2>/dev/null || true)

while IFS= read -r match; do
	path="${match%%:*}"
	rest="${match#*:}"
	line="${rest%%:*}"
	report absolute-home "$path" "machine-shaped home path at line $line" "$match"
done < <(git -C "$ROOT" grep -I -n -E -e '/Users/[[:alnum:]_.-]+/' -e '/home/[[:alnum:]_.-]+/' -- agents/shared 2>/dev/null || true)

LOCK="$ROOT/agents/shared/third-party-skills.lock.json"
if [[ ! -f "$LOCK" ]]; then
	report third-party-provenance "agents/shared/third-party-skills.lock.json" "lockfile missing"
elif ! jq -e '
	.version == 1 and
	(.skills | type == "object") and
	all(.skills | to_entries[];
		(.value.source | type == "string") and
		(.value.sourceUrl | test("^https://github\\.com/.+\\.git$")) and
		(.value.ref | test("^[0-9a-f]{40}$")) and
		(.value.gitTree | test("^[0-9a-f]{40}$")) and
		(.value.skillPath | test("(^|/)SKILL\\.md$"))
	)
' "$LOCK" >/dev/null; then
	report third-party-provenance "agents/shared/third-party-skills.lock.json" "entry lacks immutable source, revision, tree, or skill path"
fi

if [[ -f "$LOCK" ]]; then
	while IFS= read -r patch; do
		[[ -f "$ROOT/agents/shared/$patch" ]] \
			|| report third-party-provenance "agents/shared/$patch" "lock references missing patch"
	done < <(jq -r '.skills[].patch // empty' "$LOCK")

	while IFS= read -r tracked_patch; do
		relative="${tracked_patch#agents/shared/}"
		jq -e --arg patch "$relative" 'any(.skills[]; .patch == $patch)' "$LOCK" >/dev/null \
			|| report third-party-provenance "$tracked_patch" "patch is not attributed by the lockfile"
	done < <(git -C "$ROOT" ls-files 'agents/shared/third-party-patches/*')
fi

while IFS= read -r package; do
	[[ -z "$package" ]] && continue
	vendor_root="agents/shared/vendor/$package"
	license_path="$(git -C "$ROOT" ls-files "$vendor_root/LICENSE*" | head -1)"
	if [[ -z "$license_path" || ! -f "$ROOT/$vendor_root/PROVENANCE.md" ]]; then
		report third-party-license "$vendor_root" "vendored material requires LICENSE and PROVENANCE.md"
		continue
	fi
	if ! grep -Eq '^Source: https://' "$ROOT/$vendor_root/PROVENANCE.md" \
		|| ! grep -Eq '^Revision: [0-9a-f]{40}$' "$ROOT/$vendor_root/PROVENANCE.md"; then
		report third-party-license "$vendor_root/PROVENANCE.md" "provenance must record source URL and immutable revision"
	fi
done < <(git -C "$ROOT" ls-files 'agents/shared/vendor/*' | awk -F/ 'NF >= 4 {print $4}' | sort -u)

if [[ -n "$BASE" ]]; then
	git -C "$ROOT" rev-parse --verify "$BASE^{commit}" >/dev/null \
		|| { echo "FAIL: size-gate base ref not found: $BASE" >&2; exit 1; }
	git -C "$ROOT" rev-parse --verify "$HEAD^{commit}" >/dev/null \
		|| { echo "FAIL: size-gate head ref not found: $HEAD" >&2; exit 1; }

	read -r files added changed < <(
		git -C "$ROOT" diff --numstat "$BASE" "$HEAD" | awk '
			BEGIN { files = 0; added = 0; changed = 0 }
			{ files += 1; if ($1 != "-") added += $1; if ($1 != "-") changed += $1; if ($2 != "-") changed += $2 }
			END { print files, added, changed }
		'
	)
	printf 'PR size: files=%s added=%s changed=%s (limits %s/%s/%s)\n' \
		"$files" "$added" "$changed" "$MAX_FILES" "$MAX_ADDED" "$MAX_CHANGED"
	if (( files > MAX_FILES || added > MAX_ADDED || changed > MAX_CHANGED )); then
		if [[ "$APPROVED_LARGE" == "1" ]]; then
			printf 'ALLOW: large change explicitly approved\n'
		else
			report oversized-change "$BASE..$HEAD" "add large-public-change-approved after maintainer review"
		fi
	fi
fi

if (( failures > 0 )); then
	printf 'Public safety check failed with %s finding(s).\n' "$failures" >&2
	exit 1
fi

printf 'OK: public safety checks passed\n'
