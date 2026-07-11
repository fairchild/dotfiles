#!/usr/bin/env bun
/**
 * Analyze repository for release readiness.
 * Read-only - safe to run anytime.
 *
 * Usage: bun analyze.ts [--json]
 */

import { $ } from "bun";

interface Commit {
  hash: string;
  type: string;
  scope?: string;
  description: string;
  breaking: boolean;
}

interface AnalysisResult {
  context: {
    worktree: boolean;
    branch: string;
    target: string;
    repo: string;
  };
  lastTag: string | null;
  commits: Commit[];
  suggestedVersion: string;
  changelog: string;
  ciStatus: "success" | "failure" | "pending" | "unknown";
  errors: string[];
}

async function exec(cmd: string): Promise<string> {
  try {
    const result = await $`sh -c ${cmd}`.quiet().text();
    return result.trim();
  } catch {
    return "";
  }
}

async function execJson<T>(cmd: string): Promise<T | null> {
  try {
    const result = await $`sh -c ${cmd}`.quiet().json();
    return result as T;
  } catch {
    return null;
  }
}

function parseConventionalCommit(message: string): Commit | null {
  // Match: type(scope)!: description or type!: description or type: description
  const match = message.match(
    /^(\w+)(?:\(([^)]+)\))?(!)?\s*:\s*(.+?)(?:\n|$)/
  );
  if (!match) {
    // Non-conventional commit - treat as misc
    return {
      hash: "",
      type: "misc",
      description: message.split("\n")[0],
      breaking: false,
    };
  }

  const [, type, scope, bang, description] = match;
  const breaking =
    !!bang || message.toLowerCase().includes("breaking change");

  return {
    hash: "",
    type: type.toLowerCase(),
    scope: scope || undefined,
    description: description.trim(),
    breaking,
  };
}

function bumpVersion(
  current: string | null,
  commits: Commit[]
): { version: string; bump: "major" | "minor" | "patch" } {
  // Parse current version or start at 0.0.0
  let [major, minor, patch] = (current?.replace(/^v/, "") || "0.0.0")
    .split(".")
    .map(Number);

  const hasBreaking = commits.some((c) => c.breaking);
  const hasFeatures = commits.some((c) => c.type === "feat");

  let bump: "major" | "minor" | "patch";

  if (hasBreaking) {
    if (major === 0) {
      // Pre-1.0: breaking changes bump minor
      minor++;
      patch = 0;
      bump = "minor";
    } else {
      major++;
      minor = 0;
      patch = 0;
      bump = "major";
    }
  } else if (hasFeatures) {
    minor++;
    patch = 0;
    bump = "minor";
  } else {
    patch++;
    bump = "patch";
  }

  return { version: `v${major}.${minor}.${patch}`, bump };
}

function generateChangelog(commits: Commit[]): string {
  const sections: Record<string, string[]> = {
    Added: [],
    Changed: [],
    Fixed: [],
    Removed: [],
    Other: [],
  };

  for (const commit of commits) {
    const entry = commit.scope
      ? `${commit.scope}: ${commit.description}`
      : commit.description;

    switch (commit.type) {
      case "feat":
        sections.Added.push(entry);
        break;
      case "fix":
        sections.Fixed.push(entry);
        break;
      case "refactor":
      case "perf":
        sections.Changed.push(entry);
        break;
      case "revert":
        sections.Removed.push(entry);
        break;
      case "docs":
      case "style":
      case "test":
      case "chore":
      case "ci":
      case "build":
        // Skip non-user-facing changes
        break;
      default:
        sections.Other.push(entry);
    }
  }

  // Build changelog text
  const lines: string[] = [];
  for (const [section, items] of Object.entries(sections)) {
    if (items.length > 0) {
      lines.push(`### ${section}`);
      for (const item of items) {
        lines.push(`- ${item}`);
      }
      lines.push("");
    }
  }

  return lines.join("\n").trim() || "No notable changes.";
}

async function analyze(): Promise<AnalysisResult> {
  const errors: string[] = [];

  // 1. Detect context
  const gitDir = await exec("git rev-parse --git-dir");
  const commonDir = await exec("git rev-parse --git-common-dir");
  const worktree = gitDir !== commonDir;
  const branch = await exec("git branch --show-current");

  // Get repo name from remote
  const remoteUrl = await exec("git remote get-url origin");
  const repoMatch = remoteUrl.match(/[:/]([^/]+\/[^/]+?)(?:\.git)?$/);
  const repo = repoMatch ? repoMatch[1] : "unknown";

  // 2. Get default branch from GitHub
  let target = "main";
  const ghData = await execJson<{ defaultBranchRef: { name: string } }>(
    "gh repo view --json defaultBranchRef"
  );
  if (ghData?.defaultBranchRef?.name) {
    target = ghData.defaultBranchRef.name;
  } else {
    errors.push("Could not detect default branch, assuming 'main'");
  }

  // 3. Fetch latest
  await exec(`git fetch origin ${target} --quiet`);

  // 4. Find last tag
  const lastTag = await exec("git tag --list 'v*' --sort=-version:refname | head -1");

  // 5. Get commits since last tag (on origin/target)
  const range = lastTag ? `${lastTag}..origin/${target}` : `origin/${target}`;
  const logOutput = await exec(
    `git log ${range} --format="%H|||%s" --no-merges`
  );

  const commits: Commit[] = [];
  if (logOutput) {
    for (const line of logOutput.split("\n")) {
      const [hash, ...msgParts] = line.split("|||");
      const message = msgParts.join("|||");
      if (hash && message) {
        const parsed = parseConventionalCommit(message);
        if (parsed) {
          parsed.hash = hash.slice(0, 7);
          commits.push(parsed);
        }
      }
    }
  }

  // 6. Suggest version
  const { version: suggestedVersion } = bumpVersion(lastTag, commits);

  // 7. Generate changelog
  const changelog = generateChangelog(commits);

  // 8. Check CI status
  let ciStatus: AnalysisResult["ciStatus"] = "unknown";
  const runs = await execJson<Array<{ conclusion: string; status: string }>>(
    `gh run list --branch ${target} --limit 1 --json conclusion,status`
  );
  if (runs && runs.length > 0) {
    const run = runs[0];
    if (run.status === "in_progress" || run.status === "queued") {
      ciStatus = "pending";
    } else if (run.conclusion === "success") {
      ciStatus = "success";
    } else if (run.conclusion === "failure") {
      ciStatus = "failure";
    }
  }

  return {
    context: { worktree, branch, target, repo },
    lastTag: lastTag || null,
    commits,
    suggestedVersion,
    changelog,
    ciStatus,
    errors,
  };
}

// Main
const jsonOutput = process.argv.includes("--json");
const result = await analyze();

if (jsonOutput) {
  console.log(JSON.stringify(result, null, 2));
} else {
  // Human-readable output
  console.log(`\n📦 Release Analysis for ${result.context.repo}\n`);
  console.log(`Context:`);
  console.log(`  Branch: ${result.context.branch}${result.context.worktree ? " (worktree)" : ""}`);
  console.log(`  Target: origin/${result.context.target}`);
  console.log(`  Last tag: ${result.lastTag || "(none - first release)"}`);
  console.log(`  CI status: ${result.ciStatus}`);
  console.log();

  if (result.commits.length === 0) {
    console.log("No commits since last release.\n");
  } else {
    console.log(`Commits (${result.commits.length}):`);
    for (const c of result.commits.slice(0, 10)) {
      const breaking = c.breaking ? " 💥" : "";
      console.log(`  ${c.hash} ${c.type}: ${c.description}${breaking}`);
    }
    if (result.commits.length > 10) {
      console.log(`  ... and ${result.commits.length - 10} more`);
    }
    console.log();

    console.log(`Suggested version: ${result.suggestedVersion}\n`);
    console.log(`Changelog preview:`);
    console.log(result.changelog.split("\n").map(l => `  ${l}`).join("\n"));
    console.log();
  }

  if (result.errors.length > 0) {
    console.log("Warnings:");
    for (const e of result.errors) {
      console.log(`  ⚠️  ${e}`);
    }
  }
}
