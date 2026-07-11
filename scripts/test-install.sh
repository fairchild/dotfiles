#!/usr/bin/env bash
#MISE description="Exercise install.sh in an isolated HOME with local fixtures"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

case "$(uname -s)" in
    Darwin) os=macos ;;
    Linux) os=linux ;;
    *) echo "SKIP: unsupported test OS"; exit 0 ;;
esac

case "$(uname -m)" in
    x86_64|amd64) arch=x64 ;;
    arm64|aarch64) arch=arm64 ;;
    *) echo "SKIP: unsupported test architecture"; exit 0 ;;
esac

platform="$os-$arch"
version="v0.0.0-fixture"
fake_mise="$tmp/fake-mise"
fixture_home="$tmp/home"
raw_root="$tmp/raw"
mkdir -p "$fixture_home" "$raw_root/install"

{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'set -eu'
    printf 'fixture_version=%s\n' "${version#v}"
    cat <<'SH'
if [ "${1:-}" = "--version" ]; then
    printf '%s\n' "$fixture_version"
    exit 0
fi
if [ "${1:-}" = "run" ] && [ "${2:-}" = "bootstrap" ]; then
    printf '%s\n' "${MISE_ENV:-missing}" >> "$HOME/.bootstrap-invocations"
    exit 0
fi
printf 'unexpected fake mise invocation: %s\n' "$*" >&2
exit 2
SH
} > "$fake_mise"
chmod +x "$fake_mise"

if command -v sha256sum >/dev/null 2>&1; then
    fake_sha="$(sha256sum "$fake_mise" | awk '{print $1}')"
else
    fake_sha="$(shasum -a 256 "$fake_mise" | awk '{print $1}')"
fi

{
    printf 'version = "%s"\n\n' "$version"
    printf '[mise.sha256]\n'
    printf '"%s" = "%s"\n' "$platform" "$fake_sha"
} > "$raw_root/install/pins.toml"

run_install() {
    HOME="$fixture_home" \
    CODESPACES=1 \
    DOTFILES_RAW_BASE="file://$raw_root" \
    DOTFILES_REPO_URL="$ROOT" \
    DOTFILES_DIR="$fixture_home/.config/dotfiles" \
    DOTFILES_MISE_DOWNLOAD_URL="file://$fake_mise" \
    PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin" \
		"$ROOT/install.sh"
}

run_install
run_install

[[ -d "$fixture_home/.config/dotfiles/.git" ]] \
    || { echo "FAIL: installer did not create the canonical checkout" >&2; exit 1; }
[[ -x "$fixture_home/.local/bin/mise" ]] \
    || { echo "FAIL: installer did not place verified mise in ~/.local/bin" >&2; exit 1; }
[[ "$(wc -l < "$fixture_home/.bootstrap-invocations" | tr -d ' ')" == "2" ]] \
    || { echo "FAIL: repeated install did not invoke bootstrap twice" >&2; exit 1; }
[[ "$(sort -u "$fixture_home/.bootstrap-invocations")" == "codespace" ]] \
    || { echo "FAIL: installer did not propagate the detected profile" >&2; exit 1; }

printf 'OK: isolated installer fixture passed (including repeat run)\n'
