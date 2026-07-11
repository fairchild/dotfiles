#!/bin/sh
# install.sh — bootstrap entry point. Idempotent.
#
# Usage:
#     curl -fsSL https://raw.githubusercontent.com/fairchild/dotfiles/master/install.sh | sh
#
# Steps:
#   1. Detect OS + arch + profile (mac-personal, codespace, cloud-vm).
#   2. Download pinned mise binary; verify SHA256 against install/pins.toml.
#      (Pins fetched from this repo, not from GitHub releases.)
#   3. Install mise to $HOME/.local/bin/mise.
#   4. Clone repo to ~/.config/dotfiles if absent (idempotent — never updates).
#   5. Hand off to `mise run bootstrap` inside the clone.
#
# Anything beyond mise + git is the bootstrap task's problem, not this script's.
# This file stays POSIX sh — no bash-isms — so it runs on stripped-down VMs.

set -eu

REPO_URL="${DOTFILES_REPO_URL:-https://github.com/fairchild/dotfiles.git}"
RAW_BASE="${DOTFILES_RAW_BASE:-https://raw.githubusercontent.com/fairchild/dotfiles/master}"
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
GIT_REF="${DOTFILES_GIT_REF:-}"
LOCAL_BIN="$HOME/.local/bin"

log()  { printf '\033[36m==>\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[31mFAIL:\033[0m %s\n' "$*" >&2; exit 1; }

# --- 1. detect platform ---
case "$(uname -s)" in
    Darwin) os="macos" ;;
    Linux)  os="linux" ;;
    *)      fail "unsupported OS: $(uname -s)" ;;
esac

case "$(uname -m)" in
    x86_64|amd64)   arch="x64" ;;
    arm64|aarch64)  arch="arm64" ;;
    *) fail "unsupported arch: $(uname -m)" ;;
esac

platform="$os-$arch"

# Pick a profile so subsequent `mise run bootstrap` knows what we're on.
if [ -n "${DOTFILES_PROFILE:-}" ]; then
    profile="$DOTFILES_PROFILE"
elif [ -n "${CODESPACES:-}" ]; then
    profile="codespace"
elif [ "$os" = "macos" ]; then
    profile="mac-personal"
else
    profile="cloud-vm"
fi

case "$os:$profile" in
    macos:mac-personal|linux:codespace|linux:cloud-vm) ;;
    *) fail "unsupported platform/profile pair: $os/$profile" ;;
esac
export MISE_ENV="$profile"
log "platform=$platform profile=$profile"

# --- 2. pin lookup ---
# Don't depend on a TOML parser — pins.toml is small, awk is enough.
PINS_URL="$RAW_BASE/install/pins.toml"
PINS_TMP="$(mktemp)"
trap 'rm -f "$PINS_TMP"' EXIT INT TERM

curl -fsSL "$PINS_URL" -o "$PINS_TMP" || fail "could not fetch $PINS_URL"

mise_version="$(awk -F'"' '/^version/ {print $2; exit}' "$PINS_TMP")"
[ -n "$mise_version" ] || fail "could not parse mise version from pins.toml"

expected_sha="$(awk -v key="\"$platform\"" '$1 == key { gsub(/"/, "", $3); print $3; exit }' "$PINS_TMP")"
[ -n "$expected_sha" ] || fail "no SHA256 pinned for platform $platform in pins.toml"

log "pinning mise $mise_version ($platform)"

# --- 3. download + verify mise ---
binary_name="mise-$mise_version-$platform"
download_url="${DOTFILES_MISE_DOWNLOAD_URL:-https://github.com/jdx/mise/releases/download/$mise_version/$binary_name}"

mkdir -p "$LOCAL_BIN"
mise_target="$LOCAL_BIN/mise"

if [ -x "$mise_target" ] && \
   "$mise_target" --version 2>/dev/null | grep -q "${mise_version#v}"; then
    log "mise $mise_version already installed at $mise_target"
else
    download_tmp="$(mktemp)"
    log "downloading $download_url"
    curl -fsSL "$download_url" -o "$download_tmp" || fail "download failed"

    if command -v sha256sum >/dev/null 2>&1; then
        actual_sha="$(sha256sum "$download_tmp" | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1; then
        actual_sha="$(shasum -a 256 "$download_tmp" | awk '{print $1}')"
    else
        fail "no sha256sum or shasum available — cannot verify download"
    fi

    if [ "$actual_sha" != "$expected_sha" ]; then
        rm -f "$download_tmp"
        fail "SHA256 mismatch
       expected: $expected_sha
       got:      $actual_sha
       Refusing to install. Verify pins.toml is current; the bumper workflow
       runs weekly and may have a newer pin."
    fi

    mv "$download_tmp" "$mise_target"
    chmod +x "$mise_target"
    log "installed mise $mise_version → $mise_target (verified)"
fi

# Make sure subsequent commands see it.
case ":$PATH:" in
    *":$LOCAL_BIN:"*) ;;
    *) PATH="$LOCAL_BIN:$PATH"; export PATH ;;
esac

# --- 4. clone repo ---
if [ -d "$DOTFILES_DIR/.git" ]; then
    log "$DOTFILES_DIR already present — leaving as-is (run \`mise run sync\` to update)"
else
    if [ -e "$DOTFILES_DIR" ]; then
        fail "$DOTFILES_DIR exists but is not a git checkout — refusing to overwrite"
    fi
    log "cloning $REPO_URL → $DOTFILES_DIR"
    mkdir -p "$(dirname "$DOTFILES_DIR")"
    git clone "$REPO_URL" "$DOTFILES_DIR"
fi

if [ -n "$GIT_REF" ]; then
    log "checking out exact source ref $GIT_REF"
    git -C "$DOTFILES_DIR" fetch --depth=1 origin "$GIT_REF"
    git -C "$DOTFILES_DIR" checkout --detach FETCH_HEAD
    export DOTFILES_EXPECTED_GIT_REF="$GIT_REF"
fi

# --- 5. hand off to mise run bootstrap ---
cd "$DOTFILES_DIR"
log "trusting cloned mise configuration"
"$mise_target" trust "$DOTFILES_DIR/.mise.toml"
log "handing off to: mise run bootstrap (profile=$profile)"
exec "$mise_target" run bootstrap
