# 60-prompt.zsh — prompt initialization. Truly last among PATH-affecting fragments.
# Starship reads $PATH at init time to detect available tools, so this MUST run
# after every tool fragment that contributes to PATH (see 50-tools.zsh).
# 99-local.zsh runs after this for machine-specific tweaks but must not write
# to PATH.

if command -v starship &>/dev/null; then
    eval "$(starship init zsh)"
fi
