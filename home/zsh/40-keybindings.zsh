# 40-keybindings.zsh — keymap mode + history search bindings.
#
# We keep two history-search systems on purpose:
#   ^R           = incremental pattern (zsh's built-in, custom widget below).
#                  Best when you remember a substring anywhere in the command.
#   ^[[A / ^[[B  = up/down arrow substring-from-prefix search.
#                  Best when you remember the start of the command.
#
# Both are cheap. They don't conflict — different keys, different mental models.

# Emacs editing mode (matters for default keybindings).
bindkey -e

# ^R: incremental pattern search starting from the current line buffer.
history-incremental-pattern-search-backward-from-line() {
    zle history-incremental-pattern-search-backward $BUFFER
}
zle -N history-incremental-pattern-search-backward-from-line
bindkey -M viins   "^R" history-incremental-pattern-search-backward-from-line
bindkey -M vicmd   "^R" history-incremental-pattern-search-backward-from-line
bindkey -M isearch "^R" history-incremental-pattern-search-backward

# Up/Down: substring-from-prefix search (zsh built-in).
# (Previously this attempted to source zsh-history-substring-search via an
# Oh-My-Zsh path that doesn't exist on this machine. The bundled fallback is
# functionally equivalent for the common case and has no install dependency.)
bindkey '^[[A' up-line-or-beginning-search
bindkey '^[[B' down-line-or-beginning-search
autoload -U up-line-or-beginning-search
autoload -U down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
