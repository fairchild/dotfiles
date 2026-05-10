# 10-completions.zsh — lazy completion stubs for slow tools.
# kubectl/terraform/aws completions are expensive; load on first invocation.

function _dotfiles_load_completions() {
    [[ $commands[kubectl] ]] && source <(kubectl completion zsh)
    autoload -U +X bashcompinit && bashcompinit

    if type brew &>/dev/null; then
        FPATH=$(brew --prefix)/share/zsh-completions:$FPATH
        [[ -f /opt/homebrew/bin/aws_completer ]] && complete -C '/opt/homebrew/bin/aws_completer' aws
        [[ -f /opt/homebrew/bin/terraform ]] && complete -o nospace -C /opt/homebrew/bin/terraform terraform
    fi
}

for _cmd in kubectl terraform aws; do
    eval "$_cmd() { unfunction $_cmd; _dotfiles_load_completions; $_cmd \$@ }"
done
unset _cmd
