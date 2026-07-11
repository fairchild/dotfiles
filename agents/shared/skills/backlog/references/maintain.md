# Maintain — buckets and prompts

Mechanical maintenance for the backlog. The `maintain` verb (defined in `worker.md`) walks the buckets below and surfaces work needing attention; nothing moves automatically — the operator decides what to act on. For thinking-shaped work like reflecting on priorities or editing the roadmap, see `reflect.md` instead.

## When to maintain

- After merging a PR that resolved a task
- Start of a session, before claiming
- Weekly hygiene
- Whenever in-flight dirs feel suspicious

## The prompt

When the user asks to maintain the backlog, walk each bucket below and print what you find. End with a counts-only "OK" line for everything else. In-flight dirs are enumerated by exclusion (anything under `backlog/` that isn't `inbox/`, `todo/`, `done/`, or `failed/`). Use `find -L` so symlinked in-flight dirs (e.g. `maildir-shared`'s `doing → git-common-dir`) are included. Recipes assume bash — under zsh, prepend `setopt nullglob` so empty in-flight dirs don't error on glob expansion.

### `ADVANCED BUT NOT MOVED` (safe to auto-fix)

A file in an in-flight dir whose log has an `advanced to=done` line. The work was marked as completing the pipeline but the `git mv` to `done/` never ran — strict invariant violation, unambiguous.

```bash
for d in $(find -L backlog -mindepth 1 -maxdepth 1 -type d ! -name inbox ! -name todo ! -name done ! -name failed); do
  for f in "$d"/*.md; do
    [[ -f "$f" ]] || continue
    grep -q '^- .*advanced to=done' "$f" && echo "ADVANCED BUT NOT MOVED: $f"
  done
done
```

Suggested fix: run `git mv` to `done/` directly (the completion is already recorded in the log; no new log line needed). Safe because the `advanced to=done` line is the proof. (A file whose *branch* shipped but never wrote an `advanced to=done` line will surface in `TIMED OUT` once the budget expires.)

### `TIMED OUT`

A file in any in-flight dir where `now - latest_claim_line > timeout`. The task itself declared the budget — or inherits the `7d` skill-level default if no `timeout:` is in frontmatter. Latest claim line = most recent `advanced` or `rescued`.

```bash
now=$(date -u +%s)
for d in $(find -L backlog -mindepth 1 -maxdepth 1 -type d ! -name inbox ! -name todo ! -name done ! -name failed); do
  for f in "$d"/*.md; do
    [[ -f "$f" ]] || continue
    timeout=$(awk '/^---$/{n++; if(n==2) exit} n==1 && /^timeout:/ {sub(/^timeout:[[:space:]]*/, ""); print; exit}' "$f")
    [[ -z "$timeout" ]] && timeout=7d  # skill-level default
    last=$(grep -E '^- [0-9TZ:-]+ (advanced|rescued) ' "$f" | tail -1 | awk '{print $2}')
    [[ -z "$last" ]] && continue
    # Parse timeout: 4h, 3d, 2w
    n="${timeout%[smhdw]*}"; unit="${timeout: -1}"
    case "$unit" in s) secs=$n;; m) secs=$((n*60));; h) secs=$((n*3600));; d) secs=$((n*86400));; w) secs=$((n*604800));; *) continue;; esac
    last_epoch=$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$last" +%s 2>/dev/null || gdate -d "$last" +%s 2>/dev/null || true)
    [[ -z "$last_epoch" ]] && continue
    [[ $((now - last_epoch)) -gt $secs ]] && echo "TIMED OUT: $f (claimed/advanced $last, budget $timeout)"
  done
done
```

Maintain may auto-fail entries in this bucket — the timeout was author-authorized (or the documented default), so enforcing it is contract-keeping.

Suggested action: `fail` with a `timeout: ...` reason. An operator can `retry` later if the task is still worth doing. See `parallel-agents.md` for the advance-prelude vs janitor patterns.

### `UNRESOLVABLE DEPS`

A file in `todo/` or any in-flight dir referencing a `dependencies:` slug that doesn't exist anywhere in the tree. Usually a typo or rename.

```bash
in_flight=$(find -L backlog -mindepth 1 -maxdepth 1 -type d ! -name inbox ! -name todo ! -name done ! -name failed)
for d in backlog/todo $in_flight; do
  for f in "$d"/*.md; do
    [[ -f "$f" ]] || continue
    # Extract dep slugs from block-form dependencies:
    deps=$(awk '/^---$/{n++; if(n==2) exit} n==1 && /^dependencies:[[:space:]]*$/ {block=1; next} block && /^[[:space:]]/ {sub(/^[[:space:]]+/, ""); sub(/:.*/, ""); print} block && !/^[[:space:]]/ {block=0}' "$f")
    for dep in $deps; do
      if ! find backlog -name "${dep}.md" -type f | grep -q .; then
        echo "UNRESOLVABLE DEPS: $f → $dep"
      fi
    done
  done
done
```

Suggested fix: edit the file and either fix the slug or remove the dep.

### `CYCLES`

The dependency graph (across `todo/` and any in-flight dir) has a cycle. Auto-pick refuses to schedule anything in a cycle.

Sketch: for each file in `todo/` + in-flight dirs, treat its `dependencies:` map as outgoing edges to those slugs. Run DFS from each unvisited node, marking nodes *in-stack* on entry and *done* on exit; an edge to an *in-stack* node is a back-edge — report it as `a → b → c → a`.

For ≤20 active tasks the agent does this in head. For larger graphs, write the edges to scratch and walk explicitly.

### `OK`

Everything else. Print counts only:

```bash
todo=$(find backlog/todo -name '*.md' -type f | wc -l | tr -d ' ')
in_flight=$(find -L backlog -mindepth 2 -maxdepth 2 -name '*.md' -type f ! -path 'backlog/todo/*' ! -path 'backlog/done/*' ! -path 'backlog/failed/*' | wc -l | tr -d ' ')
echo "OK: $todo in todo/, $in_flight in-flight (after subtracting items surfaced above)"
```

Maintain itself never moves files (one exception: it may fail author-authorized TIMED OUT entries — see `parallel-agents.md`). Operator runs the walk, acts on each bucket via its suggested action.
