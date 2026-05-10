# ~/.zshrc → ~/.config/dotfiles/home/.zshrc (symlink installed by `mise run install:zsh`).
# Composer only. All real logic lives in numbered fragments under home/zsh/.
# Per-machine overrides go in ~/.zshrc.local (sourced by 99-local.zsh).

DOTFILES_ZSH="${DOTFILES_DIR:-$HOME/.config/dotfiles}/home/zsh"
for f in "$DOTFILES_ZSH"/*.zsh; do
    [[ -r "$f" ]] && source "$f"
done
unset DOTFILES_ZSH f
