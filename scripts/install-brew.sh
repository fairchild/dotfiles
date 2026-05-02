#!/usr/bin/env bash
#MISE description="Install packages from the active profile's Brewfile"
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"

# --- profile selection ---
profile="${MISE_ENV:-}"
if [[ -z "$profile" ]]; then
    if [[ -n "${CODESPACES:-}" ]]; then
        profile="codespace"
    elif [[ "$(uname)" == "Darwin" ]]; then
        profile="mac-personal"
    else
        profile="cloud-vm"
    fi
fi

case "$profile" in
    mac-personal)   brewfile="$DOTFILES_DIR/home/Brewfile" ;;
    codespace)      brewfile="$DOTFILES_DIR/home/Brewfile.codespace" ;;
    cloud-vm|linux-personal) brewfile="$DOTFILES_DIR/home/Brewfile.cloud-vm" ;;
    *)
        echo "FAIL: unknown profile '$profile'" >&2
        echo "       Set MISE_ENV to one of: mac-personal, codespace, cloud-vm, linux-personal" >&2
        exit 2
        ;;
esac

if [[ ! -f "$brewfile" ]]; then
    echo "FAIL: $brewfile missing for profile $profile" >&2
    exit 2
fi
echo "OK: profile=$profile brewfile=$brewfile"

# --- brew availability ---
if ! command -v brew &>/dev/null; then
    if [[ "$(uname)" == "Linux" ]]; then
        cat >&2 <<'EOF'
FAIL: brew not on PATH and no Linuxbrew install detected.

On Linux, install Linuxbrew first:
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

Or, if Linuxbrew is undesirable, the rough translation table for what we'd
otherwise install:

    Brewfile        Debian/Ubuntu apt
    --------        ----------------
    mise            curl https://mise.run | sh   (handles itself)
    gh              gh (apt repo: cli.github.com)
    jq              jq
    fd              fd-find             (binary 'fdfind' — alias to 'fd')
    ripgrep         ripgrep
    fzf             fzf
    starship        curl -sS https://starship.rs/install.sh | sh
    zoxide          zoxide
    watchexec       watchexec           (cargo install if too old)
    tmux            tmux
    gcc/make        build-essential

Re-run `mise run install:brew` after either installing Linuxbrew or
manually using the table above.
EOF
        exit 1
    fi
    echo "FAIL: brew not on PATH on macOS — install from https://brew.sh first" >&2
    exit 1
fi

# --- run bundle ---
echo "OK: brew $(brew --version | head -1)"
echo "Running: brew bundle --file=$brewfile"
brew bundle --file="$brewfile"
