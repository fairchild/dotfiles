# legacy/ — the dry dock

Parked planks from the pre-umbrella life of this repo. Kept tracked rather
than deleted, on the principle that the ship metaphor needs a place to put
the old wood. Nothing in here is sourced by the live shell or any task in
the umbrella. If you want to resurrect a snippet, copy it into the
appropriate `home/zsh/*.zsh` fragment with a comment about why.

## Contents

| Plank | Original purpose | Why retired |
|---|---|---|
| `.bash_profile`, `.bashrc`, `.bash_prompt`, `.exports`, `.inputrc` | Bash daily-driver setup | Shell is now zsh. New layout: `home/.zshrc` + `home/zsh/*.zsh`. |
| `.vim/`, `.vimrc`, `.gvimrc` | Vim daily-driver setup | Vim no longer the daily editor; replaced by smart-editor + IDEs. |
| `.osx` | "Sensible OS X defaults" sweep | Mathiasbynens-vintage; many `defaults write` keys bitrotted across macOS versions (Mavericks → present). Run selectively if at all. |
| `.brew` | One-shot brew install script | Superseded by per-profile Brewfiles under `home/Brewfile{,.codespace,.cloud-vm}`. |
| `.screenrc` | GNU screen config | tmux/wezterm/IDE replaced this workflow. |
| `.hgignore`, `.wgetrc`, `.hushlogin`, `.gitattributes` | Tools no longer in regular use | hg → git; wget → curl; trivial. |
| `bootstrap.sh` | rsync `.* → $HOME` deploy | Replaced by `scripts/install-zsh.sh`, `install-git.sh`, etc. — symlink-based, idempotent, with explicit backup. |
| `README.original.md` | mathiasbynens's upstream README | Preserved verbatim for attribution + the `~/.extra` example. |

## Licensing

The contents of this directory are derivatives of, or copies from,
[mathiasbynens/dotfiles](https://github.com/mathiasbynens/dotfiles) and the
upstream contributors listed in `README.original.md`. mathiasbynens's repo
does not carry a formal `LICENSE` file but is publicly distributed; the
fork-then-detach lineage is recorded both in this repo's git history and in
the root `LICENSE` file's first copyright line. Vim color and syntax files
under `legacy/.vim/colors/` and `legacy/.vim/syntax/` carry their own author
headers (Tomas Restrepo for `molokai.vim`, Jeroen Ruigrok van der Werven
for `json.vim`).

If you fork *this* repo and want to strip the dry dock entirely, removing
the `legacy/` directory is safe — nothing in the live config sources from
it. The umbrella was deliberately designed so that keel and planks are
disjoint.
