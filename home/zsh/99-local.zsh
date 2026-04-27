# 99-local.zsh — sources machine-specific config, last in the chain.
# Two paths supported (in order):
#   1. ~/.zshrc.local             — preferred, copied from .zshrc.local.example.
#   2. ~/.zshrc_machine_specific  — legacy name still honored.
# Anything that should never be committed (private aliases, work tokens,
# experimental tweaks) lives in one of these.
#
# Hard rule: do not write to PATH from this fragment if you want starship to
# pick it up. PATH writes must happen earlier than 60-prompt.zsh.

[[ -f ~/.zshrc.local ]] && source ~/.zshrc.local
[[ -f ~/.zshrc_machine_specific ]] && source ~/.zshrc_machine_specific
