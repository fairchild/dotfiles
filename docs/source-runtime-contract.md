# Public source and private runtime

This repository is a public specification that produces local runtime. The boundary is based on ownership, not whether a path happens to be ignored by Git.

## The three classes

| Class | Examples | Authority | Disposal and backup |
|---|---|---|---|
| Public source | `~/.config/dotfiles/home/`, `agents/shared/first-party-skills/`, the third-party lock and patches | Git is authoritative; changes are reviewed and shareable | Re-clonable. Do not back up generated copies as user data. |
| Generated runtime | `~/.agents/skills/`, managed third-party copies, `~/.pi/agent/skills` link | Installer plus public source are authoritative | Re-creatable. Unknown or unmanaged collisions are backed up before replacement. |
| Private machine-local state | `~/.gitconfig.local`, `~/.zshrc.local`, credentials, runtime logs, `~/.claude` generated state | The local machine or owning application is authoritative | Never overwrite. Preserve during migration and exclude from public Git. |

An ignored path inside the public checkout is still on the wrong side of the boundary. Generated runtime belongs outside the checkout so Git status and publication checks do not have to distinguish intentional runtime from accidental disclosure.

## Symlink policy

A public read-only asset may be linked into runtime when its consumer only reads it. First-party skill directories, shared prompts, shared helper scripts, and the shell base configuration fit this rule.

A path that an application may mutate must be a real private file or directory, or a private loader that includes public source. Materialized third-party skills are real generated directories marked with `.dotfiles-managed.json`; the marker is the authority to replace them on the next restore. An unmarked collision is backed up.

`~/.gitconfig` is a real private loader. It includes the tracked public Git base first and `~/.gitconfig.local` last, so `git config --global` writes remain private. The public shell base may remain linked because zsh reads it and writes private customization to `~/.zshrc.local`.

## Agent runtime migration

`mise run install:agents` performs an idempotent migration:

1. Replace the legacy `~/.agents -> <checkout>/agents/shared` symlink with a real `~/.agents/` directory.
2. Move ignored `agents/shared/skills/` and `agents/shared/runtime-backups/` out of the checkout into `~/.local/share/dotfiles/migration-backups/`.
3. Link public read-only prompts and scripts into `~/.agents/`.
4. Link first-party skill entries to public source and restore third-party entries from the immutable lock into real generated directories.
5. Back up every unmanaged collision before changing it.
6. Point Pi at the generated `~/.agents/skills` directory.

Repeated runs leave correct links in place and replace only directories carrying a matching managed marker.

## Participant contract

A participant declares its public source checkout and runtime path separately. Doctor checks classify drift rather than requiring a mutable runtime directory to be pristine:

- tracked source drift is reviewable work;
- known generated/private runtime is allowed;
- an unknown path or write-through link is a warning or failure until classified.

Bootstrap creates or migrates runtime without pulling private state into source. Sync updates public source, rematerializes generated runtime, and then runs doctor. The fail-closed sequence and offline mode are documented in [`sync.md`](sync.md).
