# 50-tools.zsh — vendor tool integration, PATH writes, env setup.
# Everything that touches PATH or sources tool-specific completions lives here.
# Nothing after this fragment (60-prompt, 99-local) should write to PATH —
# starship init in 60-prompt.zsh is the last consumer of the assembled PATH.

# --- editor ---
# Smart editor when local; vim over SSH (smart-editor often opens a GUI).
if [[ -n $SSH_CONNECTION ]]; then
    export EDITOR='vim'
else
    export EDITOR="$HOME/.local/bin/smart-editor"
    export VISUAL="$HOME/.local/bin/smart-editor"
fi

# --- $HOME/.local/bin (user-local installs) ---
export PATH="$HOME/.local/bin:$PATH"

# --- mise (runtime + task manager) ---
if command -v mise &>/dev/null; then
    eval "$(mise activate zsh)"
    [[ -f "$HOME/code/claude-code/mise-hooks.zsh" ]] && source "$HOME/code/claude-code/mise-hooks.zsh"
fi

# --- pnpm ---
export PNPM_HOME="$HOME/Library/pnpm"
case ":$PATH:" in
    *":$PNPM_HOME:"*) ;;
    *) export PATH="$PNPM_HOME:$PATH" ;;
esac

# --- bun ---
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
[ -s "$BUN_INSTALL/_bun" ] && source "$BUN_INSTALL/_bun"

# --- LM Studio CLI ---
[[ -d "$HOME/.lmstudio/bin" ]] && export PATH="$PATH:$HOME/.lmstudio/bin"

# --- Antigravity ---
[[ -d "$HOME/.antigravity/antigravity/bin" ]] && export PATH="$HOME/.antigravity/antigravity/bin:$PATH"

# --- turso ---
[ -f "$HOME/.turso/env" ] && . "$HOME/.turso/env"

# --- fzf ---
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# --- fzf-tab styles ---
zstyle ':completion:*' menu no
zstyle ':completion:*' list-colors ${(s.:.)LS_COLORS}
zstyle ':completion:*:descriptions' format '[%d]'

# --- kiro shell integration (when running inside kiro) ---
[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path zsh)"

# --- Claude Code skills: git worktree CLI (wt) ---
[ -f "$HOME/.claude/skills/git-worktree/scripts/wt.zsh" ] && \
    source "$HOME/.claude/skills/git-worktree/scripts/wt.zsh"
