# 00-options.zsh — zsh shell options, completion bootstrap, history.
# Loaded first. No PATH writes, no tool init.

autoload -Uz compinit

# Auto-rehash when PATH changes.
zstyle ':completion:*' rehash true

# Cache compinit unless older than 24h.
if [[ -n ~/.zcompdump(#qN.mh+24) ]]; then
    compinit
else
    compinit -C
fi

# Menu-style completion + custom function dir.
zstyle ':completion:*' menu select
fpath+=~/.zfunc

# History: enormous, deduped, with timestamps.
export HISTFILESIZE=1000000000
export HISTSIZE=1000000000
export HISTTIMEFORMAT="[%F %T] "
setopt INC_APPEND_HISTORY
setopt EXTENDED_HISTORY
setopt HIST_FIND_NO_DUPS
setopt HIST_IGNORE_ALL_DUPS
