#!/usr/bin/env bash
#MISE description="Fast-forward public source, rematerialize runtime, and run doctor"
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
REMOTE="${DOTFILES_SYNC_REMOTE:-origin}"
BRANCH="${DOTFILES_SYNC_BRANCH:-master}"
offline=0
first_party_only=0

while [[ $# -gt 0 ]]; do
	case "$1" in
		--offline) offline=1; first_party_only=1; shift ;;
		--first-party-only) first_party_only=1; shift ;;
		-h|--help)
			printf 'usage: %s [--offline|--first-party-only]\n' "$0"
			exit 0
			;;
		*) echo "unknown option: $1" >&2; exit 2 ;;
	esac
done

fail() {
	printf 'FAIL: %s\n' "$*" >&2
	exit 1
}

[[ -d "$DOTFILES_DIR/.git" || -f "$DOTFILES_DIR/.git" ]] \
	|| fail "$DOTFILES_DIR is not a Git checkout"

current_branch="$(git -C "$DOTFILES_DIR" branch --show-current)"
[[ "$current_branch" == "$BRANCH" ]] \
	|| fail "checkout is on '$current_branch', expected '$BRANCH'; switch branches or set DOTFILES_SYNC_BRANCH intentionally"

if [[ -n "$(git -C "$DOTFILES_DIR" status --porcelain --untracked-files=normal)" ]]; then
	fail "public source has local changes; commit, move, or intentionally discard them before sync"
fi

target_ref="$REMOTE/$BRANCH"
if (( offline )); then
	echo "OFFLINE: using existing $target_ref without network fetch"
else
	echo "FETCH: $REMOTE"
	git -C "$DOTFILES_DIR" fetch --quiet --prune "$REMOTE" \
		|| fail "fetch failed; retry with network access or use --offline with an existing remote-tracking ref"
fi

git -C "$DOTFILES_DIR" show-ref --verify --quiet "refs/remotes/$target_ref" \
	|| fail "remote-tracking ref is missing: $target_ref"

read -r ahead behind < <(git -C "$DOTFILES_DIR" rev-list --left-right --count "HEAD...$target_ref")
if (( ahead > 0 && behind > 0 )); then
	fail "source diverged from $target_ref ($ahead ahead, $behind behind); reconcile in a development checkout"
elif (( ahead > 0 )); then
	fail "source is $ahead commit(s) ahead of $target_ref; publish or move those commits before sync"
elif (( behind > 0 )); then
	echo "FAST-FORWARD: $behind commit(s) from $target_ref"
	git -C "$DOTFILES_DIR" merge --ff-only "$target_ref"
else
	echo "SOURCE: already current at $target_ref"
fi

if (( first_party_only )); then
	echo "MATERIALIZE: first-party runtime only"
	DOTFILES_SKIP_THIRD_PARTY_SKILLS=1 "$DOTFILES_DIR/scripts/install-agents.sh"
else
	echo "MATERIALIZE: first-party sources and pinned third-party runtime"
	"$DOTFILES_DIR/scripts/install-agents.sh"
fi

echo "DOCTOR: checking converged installation"
set +e
"$DOTFILES_DIR/scripts/doctor.sh"
doctor_status=$?
set -e
if (( doctor_status != 0 )); then
	printf 'SYNC: doctor returned status %s\n' "$doctor_status" >&2
fi
exit "$doctor_status"
