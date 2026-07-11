#!/usr/bin/env bash
#MISE description="Exercise sync convergence and failure paths with local remotes"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
SEED="$tmp/seed"
ORIGIN="$tmp/origin.git"

mkdir -p "$SEED/scripts"
git -C "$SEED" init -q -b master
git -C "$SEED" config user.name fixture
git -C "$SEED" config user.email fixture@example.com
cp "$ROOT/scripts/sync.sh" "$SEED/scripts/sync.sh"
chmod +x "$SEED/scripts/sync.sh"
cat > "$SEED/scripts/install-agents.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${FAIL_MATERIALIZE:-0}" == "1" ]]; then
	exit 7
fi
if [[ "${DOTFILES_SKIP_THIRD_PARTY_SKILLS:-0}" == "1" ]]; then
	echo first-party >> "$HOME/materialize.log"
else
	echo all >> "$HOME/materialize.log"
fi
SH
cat > "$SEED/scripts/doctor.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo doctor >> "$HOME/doctor.log"
exit "${DOCTOR_STATUS:-0}"
SH
chmod +x "$SEED/scripts/install-agents.sh" "$SEED/scripts/doctor.sh"
printf 'fixture\n' > "$SEED/README.md"
git -C "$SEED" add .
git -C "$SEED" commit -qm initial
git init -q --bare "$ORIGIN"
git -C "$ORIGIN" symbolic-ref HEAD refs/heads/master
git -C "$SEED" remote add origin "$ORIGIN"
git -C "$SEED" push -q -u origin master

clone_client() {
	local name="$1"
	CLIENT="$tmp/client-$name"
	CLIENT_HOME="$tmp/home-$name"
	mkdir -p "$CLIENT_HOME"
	git clone -q "$ORIGIN" "$CLIENT"
	git -C "$CLIENT" config user.name fixture
	git -C "$CLIENT" config user.email fixture@example.com
}

run_sync() {
	local client="$1" fixture_home="$2"
	shift 2
	HOME="$fixture_home" DOTFILES_DIR="$client" "$client/scripts/sync.sh" "$@" >/dev/null
}

clone_client current
current_head="$(git -C "$CLIENT" rev-parse HEAD)"
run_sync "$CLIENT" "$CLIENT_HOME"
run_sync "$CLIENT" "$CLIENT_HOME"
[[ "$(git -C "$CLIENT" rev-parse HEAD)" == "$current_head" ]]
[[ "$(grep -c '^all$' "$CLIENT_HOME/materialize.log")" == "2" ]]
[[ "$(grep -c '^doctor$' "$CLIENT_HOME/doctor.log")" == "2" ]]
printf 'PASS: current source is idempotent and still rematerializes runtime\n'

clone_client updated
updated_client="$CLIENT"
updated_home="$CLIENT_HOME"
printf 'v2\n' > "$SEED/version.txt"
git -C "$SEED" add version.txt
git -C "$SEED" commit -qm update
git -C "$SEED" push -q
run_sync "$updated_client" "$updated_home"
[[ "$(git -C "$updated_client" rev-parse HEAD)" == "$(git -C "$SEED" rev-parse HEAD)" ]]
[[ -f "$updated_client/version.txt" ]]
printf 'PASS: source fast-forwards before runtime materialization\n'

clone_client offline
offline_client="$CLIENT"
offline_home="$CLIENT_HOME"
printf 'v3\n' >> "$SEED/version.txt"
git -C "$SEED" add version.txt
git -C "$SEED" commit -qm offline-update
git -C "$SEED" push -q
git -C "$offline_client" fetch -q origin
git -C "$offline_client" remote set-url origin "$tmp/unreachable.git"
run_sync "$offline_client" "$offline_home" --offline
[[ "$(git -C "$offline_client" rev-parse HEAD)" == "$(git -C "$SEED" rev-parse HEAD)" ]]
grep -q '^first-party$' "$offline_home/materialize.log"
printf 'PASS: offline mode uses existing tracking data and first-party runtime only\n'

clone_client first-party
run_sync "$CLIENT" "$CLIENT_HOME" --first-party-only
grep -q '^first-party$' "$CLIENT_HOME/materialize.log"
printf 'PASS: online first-party-only mode still fetches source\n'

clone_client dirty
printf 'dirty\n' >> "$CLIENT/README.md"
if run_sync "$CLIENT" "$CLIENT_HOME"; then
	echo "FAIL: dirty source was accepted" >&2
	exit 1
fi
[[ ! -e "$CLIENT_HOME/materialize.log" ]]
printf 'PASS: dirty source is rejected before materialization\n'

clone_client ahead
printf 'local\n' > "$CLIENT/local.txt"
git -C "$CLIENT" add local.txt
git -C "$CLIENT" commit -qm local
if run_sync "$CLIENT" "$CLIENT_HOME"; then
	echo "FAIL: unpublished local commit was accepted" >&2
	exit 1
fi
printf 'PASS: ahead source is rejected rather than silently retained\n'

clone_client materialize-failure
set +e
HOME="$CLIENT_HOME" DOTFILES_DIR="$CLIENT" FAIL_MATERIALIZE=1 "$CLIENT/scripts/sync.sh" >/dev/null 2>&1
status=$?
set -e
[[ "$status" == "7" ]]
[[ ! -e "$CLIENT_HOME/doctor.log" ]]
printf 'PASS: materialization failure propagates and skips doctor\n'

clone_client doctor-status
set +e
HOME="$CLIENT_HOME" DOTFILES_DIR="$CLIENT" DOCTOR_STATUS=2 "$CLIENT/scripts/sync.sh" >/dev/null 2>&1
status=$?
set -e
[[ "$status" == "2" ]]
[[ -f "$CLIENT_HOME/doctor.log" ]]
printf 'PASS: doctor status is preserved\n'

printf 'OK: sync convergence fixtures passed\n'
