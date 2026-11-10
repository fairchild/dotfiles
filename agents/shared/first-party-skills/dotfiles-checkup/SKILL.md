---
name: dotfiles-checkup
description: Check this machine's dotfiles against the public repo and bring them back to clean. Use when the user asks to check, tidy, or clean up their dotfiles or shell config, when a new shell prints errors, when PATH has duplicates, after installing a tool that edits ~/.zshrc, or when `mise run doctor` warns.
---

# Dotfiles checkup

`~/.config/dotfiles` is public source. `~/.zshrc` is a symlink into it, so a tool installer that appends to `~/.zshrc` writes into the public repo. This skill finds what drifted on this machine, decides where each change belongs, and hands back a pull request plus a clean local state.

`mise run doctor` does the deterministic checks. This skill adds the judgment doctor can't make: whether a change is public, private, or redundant.

## 1. Inspect

```bash
cd "${DOTFILES_DIR:-$HOME/.config/dotfiles}"
git status --short --branch
mise run doctor
```

Read every WARN and FAIL. The ones this skill handles:

- `home/.zshrc changed locally`: an installer appended to the composer.
- `fresh login shell wrote to stderr`: startup prints an error.
- `fresh login shell PATH repeats`: two writers add the same directory.
- `uncommitted changes`: inspect them; they may be someone's in-flight work.

Report other findings as they are, using the remedy doctor prints.

## 2. Triage each change

Run `git diff -- home/`. Grep `home/zsh/*.zsh` before moving any line, because many installer lines repeat something a fragment already does.

| The line is | It goes to |
| --- | --- |
| A duplicate of an existing fragment line | Deleted |
| A tool's PATH entry | `home/zsh/50-tools.zsh`, guarded with `[[ -d "$HOME/..." ]]`, `$HOME`-relative |
| A completion directory | `fpath` in `home/zsh/00-options.zsh`, before `compinit` |
| A second `compinit` | Deleted |
| An alias or a function | `home/zsh/20-aliases.zsh` or `home/zsh/30-functions.zsh` |
| Identity, hostnames, employer paths, tokens, or a trial tool | `~/.zshrc.local` (private) |

The README rule decides public versus private: machine-local identity, secrets, generated runtime, logs, and caches stay out of tracked source. Write every public line so it is harmless on a machine without the tool. PATH writes in `~/.zshrc.local` happen after starship starts, so starship will not see them.

Changes outside `home/`, such as skill edits, are not drift. Leave them alone and list them in the report.

Remove the appended lines from `home/.zshrc` with an exact edit. Restoring the file with `git checkout` or `git restore` discards work and is often blocked.

## 3. Find startup problems

- For stderr output, trace it: `env -i HOME="$HOME" TERM=xterm-256color PATH=/usr/bin:/bin zsh -xlic exit 2>&1 | tail -40`.
- For PATH duplicates, grep the directory across `home/zsh/`, `~/.zprofile`, `~/.zshenv`, and `~/.zshrc.local`. The files outside `home/zsh/` are private. Name them in the report and leave the edit to the user.

Text that reaches the terminal title or a prompt goes through `printf '%s'`, never `print -P`. With `prompt_subst` on, `print -P` runs `$(...)` found in its text.

## 4. Verify

```bash
for f in home/.zshrc home/zsh/*.zsh; do zsh -n "$f"; done
mise run doctor
mise run check:safety
```

Doctor's shell checks start a new login shell, so they test the edited files, not the shell you are running in.

## 5. Publish

Create a branch from `master`. Commit only the files this checkup changed, with a conventional message such as `fix(zsh): ...`. Open a PR and wait for its checks. Never push to `master`.

After the PR merges, each machine runs:

```bash
cd ~/.config/dotfiles && git switch master && mise run sync
```

`sync` refuses to run on a dirty checkout or a branch other than `master`. That refusal is how you know a machine has drift left to triage.

## Report

End with:
- what doctor found;
- where each change went: public, private, or deleted;
- edits left to the user in private files;
- the PR link and its check status;
- the next command to run.
