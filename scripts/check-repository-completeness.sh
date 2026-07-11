#!/usr/bin/env bash
#MISE description="Verify required public paths and local references are tracked"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" == "--root" ]]; then
	ROOT="$(cd "$2" && pwd)"
	shift 2
fi
[[ $# -eq 0 ]] || { echo "usage: $0 [--root PATH]" >&2; exit 2; }

CONTRACT="${DOTFILES_ENTRYPOINT_CONTRACT:-$ROOT/scripts/public-entrypoints.txt}"
failures=0

for command_name in git grep sed python3; do
	command -v "$command_name" >/dev/null 2>&1 \
		|| { echo "FAIL: required command not found: $command_name" >&2; exit 1; }
done
[[ -f "$CONTRACT" ]] || { echo "FAIL: public entrypoint contract missing: $CONTRACT" >&2; exit 1; }

ignore_rule_for() {
	local path="$1" detail pattern
	detail="$(git -C "$ROOT" check-ignore -v --no-index "$path" 2>/dev/null || true)"
	[[ -n "$detail" ]] || return 0
	pattern="${detail#*:*:}"
	pattern="${pattern%%$'\t'*}"
	[[ "$pattern" == !* ]] || printf '%s\n' "$detail"
}

report_missing() {
	local path="$1" reason="$2" ignore_detail
	ignore_detail="$(ignore_rule_for "$path")"
	if [[ -n "$ignore_detail" ]]; then
		printf 'FAIL: required public path is ignored: %s (%s; rule: %s)\n' "$path" "$reason" "$ignore_detail" >&2
	else
		printf 'FAIL: required public path is absent: %s (%s)\n' "$path" "$reason" >&2
	fi
	failures=$((failures + 1))
}

check_path() {
	local path="$1" reason="$2" ignore_detail tracked
	path="${path#./}"
	if [[ -z "$path" || "$path" == .. || "$path" == ../* || "$path" == /* ]]; then
		printf 'FAIL: public reference escapes repository: %s (%s)\n' "$path" "$reason" >&2
		failures=$((failures + 1))
		return
	fi

	if [[ ! -e "$ROOT/$path" && ! -L "$ROOT/$path" ]]; then
		report_missing "$path" "$reason"
		return
	fi

	if [[ -d "$ROOT/$path" ]]; then
		tracked="$(git -C "$ROOT" ls-files "$path/**" | head -1)"
	else
		tracked="$(git -C "$ROOT" ls-files --error-unmatch "$path" 2>/dev/null || true)"
	fi
	if [[ -z "$tracked" ]]; then
		report_missing "$path" "$reason"
		return
	fi

	ignore_detail="$(ignore_rule_for "$path")"
	if [[ -n "$ignore_detail" ]]; then
		printf 'FAIL: tracked public path now matches an ignore rule: %s (%s; rule: %s)\n' "$path" "$reason" "$ignore_detail" >&2
		failures=$((failures + 1))
	fi
}

while IFS='|' read -r path reason extra; do
	[[ -z "$path" || "$path" == \#* ]] && continue
	if [[ -z "$reason" || -n "$extra" ]]; then
		echo "FAIL: malformed public entrypoint line: $path|$reason${extra:+|$extra}" >&2
		exit 1
	fi
	check_path "$path" "entrypoint: $reason"
done < "$CONTRACT"

normalize_link() {
	python3 - "$1" "$2" <<'PY'
import os, sys
source, target = sys.argv[1:]
print(os.path.normpath(os.path.join(os.path.dirname(source), target)))
PY
}

while IFS= read -r source; do
	while IFS= read -r token; do
		target="${token#](}"
		target="${target%)}"
		target="${target#<}"
		target="${target%>}"
		target="${target%%#*}"
		target="${target%%\?*}"
		case "$target" in
			""|\#*|http://*|https://*|mailto:*|/*|~*) continue ;;
		esac
		resolved="$(normalize_link "$source" "$target")"
		check_path "$resolved" "relative link from $source"
	done < <(grep -Eo '\]\([^)]*\)' "$ROOT/$source" 2>/dev/null || true)
done < <(
	{
		git -C "$ROOT" ls-files README.md ROADMAP.md 'docs/*.md'
		git -C "$ROOT" ls-files agents/shared/README.md
	} | sort -u
)

if [[ -f "$ROOT/.mise.toml" ]]; then
	while IFS= read -r script_path; do
		check_path "$script_path" "script referenced by .mise.toml"
	done < <(grep -Eo '\./scripts/[A-Za-z0-9._/-]+' "$ROOT/.mise.toml" | sort -u)
fi

# shellcheck disable=SC2016 # The loop source intentionally matches a literal variable name.
while IFS= read -r reference; do
	check_path "${reference#\$DOTFILES_DIR/}" "DOTFILES_DIR reference in tracked script"
done < <(git -C "$ROOT" grep -I -h -Eo '\$DOTFILES_DIR/scripts/[A-Za-z0-9._/-]+' -- 'scripts/*.sh' 2>/dev/null | sort -u || true)

if (( failures > 0 )); then
	printf 'Repository completeness failed with %s finding(s).\n' "$failures" >&2
	exit 1
fi
printf 'OK: required public paths and local references are tracked\n'
