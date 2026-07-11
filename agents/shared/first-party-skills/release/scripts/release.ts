#!/usr/bin/env bun
/**
 * Execute a release with worktree-aware strategy.
 *
 * Usage:
 *   bun release.ts                    # Interactive release
 *   bun release.ts --dry-run          # Preview only
 *   bun release.ts --version v1.2.3   # Override version
 *   bun release.ts --no-changelog     # Skip CHANGELOG.md, notes in GH release only
 *   bun release.ts --current-branch   # Release current branch instead of default
 *   bun release.ts --skip-ci          # Skip CI status check
 *   bun release.ts --prerelease alpha # Create pre-release (e.g., v1.0.0-alpha.1)
 */

import { $ } from "bun";
import { existsSync, mkdirSync, unlinkSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

interface ReleaseOptions {
  dryRun: boolean;
  version?: string;
  noChangelog: boolean;
  currentBranch: boolean;
  skipCi: boolean;
  prerelease?: string;
}

interface AnalysisResult {
  context: {
    worktree: boolean;
    branch: string;
    target: string;
    repo: string;
  };
  lastTag: string | null;
  commits: Array<{
    hash: string;
    type: string;
    scope?: string;
    description: string;
    breaking: boolean;
  }>;
  suggestedVersion: string;
  changelog: string;
  ciStatus: "success" | "failure" | "pending" | "unknown";
  errors: string[];
}

function parseArgs(): ReleaseOptions {
  const args = process.argv.slice(2);
  const options: ReleaseOptions = {
    dryRun: false,
    noChangelog: false,
    currentBranch: false,
    skipCi: false,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--dry-run":
        options.dryRun = true;
        break;
      case "--version":
        options.version = args[++i];
        break;
      case "--no-changelog":
        options.noChangelog = true;
        break;
      case "--current-branch":
        options.currentBranch = true;
        break;
      case "--skip-ci":
        options.skipCi = true;
        break;
      case "--prerelease":
        options.prerelease = args[++i];
        break;
    }
  }

  return options;
}

async function exec(cmd: string): Promise<string> {
  try {
    const result = await $`sh -c ${cmd}`.quiet().text();
    return result.trim();
  } catch (e: unknown) {
    const error = e as { stderr?: string };
    throw new Error(error.stderr || String(e));
  }
}

function applyPrerelease(version: string, preid: string, lastTag: string | null): string {
  const base = version.replace(/^v/, "");

  // Check if last tag was a prerelease of same version
  if (lastTag) {
    const lastBase = lastTag.replace(/^v/, "").split("-")[0];
    const lastPreMatch = lastTag.match(/-(\w+)\.(\d+)$/);

    if (lastBase === base && lastPreMatch && lastPreMatch[1] === preid) {
      // Increment prerelease number
      const num = parseInt(lastPreMatch[2]) + 1;
      return `v${base}-${preid}.${num}`;
    }
  }

  // Start new prerelease
  return `v${base}-${preid}.1`;
}

function formatDate(): string {
  return new Date().toISOString().split("T")[0];
}

async function updateChangelog(
  releaseDir: string,
  version: string,
  changelog: string
): Promise<void> {
  const changelogPath = join(releaseDir, "CHANGELOG.md");
  const date = formatDate();

  const newEntry = `## [${version.replace(/^v/, "")}] - ${date}\n\n${changelog}\n\n`;

  if (existsSync(changelogPath)) {
    const content = await Bun.file(changelogPath).text();
    // Insert after "# Changelog" header
    const headerMatch = content.match(/^# Changelog\n+/);
    if (headerMatch) {
      const insertPos = headerMatch[0].length;
      const updated =
        content.slice(0, insertPos) + newEntry + content.slice(insertPos);
      await Bun.write(changelogPath, updated);
    } else {
      // No header, prepend everything
      await Bun.write(changelogPath, `# Changelog\n\n${newEntry}${content}`);
    }
  } else {
    // Create new file
    await Bun.write(changelogPath, `# Changelog\n\n${newEntry}`);
  }
}

async function createReleaseWorktree(
  target: string,
  repoName: string,
  version: string
): Promise<string> {
  // Always use ephemeral worktree for predictable, isolated releases
  // Path: ~/.worktrees/<repo>/release-<tag>
  const home = process.env.HOME || "~";
  const shortName = repoName.split("/").pop() || "repo";
  const baseDir = join(home, ".worktrees", shortName);
  const releaseDir = join(baseDir, `release-${version}`);

  if (existsSync(releaseDir)) {
    throw new Error(
      `Release worktree already exists: ${releaseDir}\n` +
      `This usually means a previous release of ${version} failed.\n` +
      `Clean up with: git worktree remove "${releaseDir}" --force`
    );
  }

  if (!existsSync(baseDir)) {
    mkdirSync(baseDir, { recursive: true });
  }

  console.log(`  Creating release worktree: ${releaseDir}`);
  await exec(`git fetch origin ${target}`);
  await exec(`git worktree add "${releaseDir}" "origin/${target}" --detach`);
  return releaseDir;
}

async function main() {
  const options = parseArgs();

  console.log("\n🚀 Release\n");

  // 1. Run analysis
  console.log("Analyzing...");
  const analyzeScript = join(__dirname, "analyze.ts");
  const analysisJson = await exec(`bun "${analyzeScript}" --json`);
  const analysis: AnalysisResult = JSON.parse(analysisJson);

  console.log(`  Branch: ${analysis.context.branch}${analysis.context.worktree ? " (worktree)" : ""}`);
  console.log(`  Target: origin/${analysis.context.target}`);
  console.log(`  Last tag: ${analysis.lastTag || "(none)"}`);
  console.log(`  Commits: ${analysis.commits.length}`);
  console.log(`  CI: ${analysis.ciStatus}`);
  console.log();

  // 2. Check CI status
  if (!options.skipCi && analysis.ciStatus === "failure") {
    console.error("❌ CI is failing on default branch. Fix CI first or use --skip-ci");
    process.exit(1);
  }

  if (!options.skipCi && analysis.ciStatus === "pending") {
    console.error("⏳ CI is still running. Wait for completion or use --skip-ci");
    process.exit(1);
  }

  // 3. Determine version
  let version = options.version || analysis.suggestedVersion;
  if (options.prerelease) {
    version = applyPrerelease(version, options.prerelease, analysis.lastTag);
  }

  console.log(`Version: ${version}`);
  console.log();

  // 4. Show changelog preview
  console.log("Changelog:");
  console.log(analysis.changelog.split("\n").map((l) => `  ${l}`).join("\n"));
  console.log();

  // 5. Dry run check
  if (options.dryRun) {
    console.log("🔍 Dry run complete. No changes made.\n");
    return;
  }

  // 6. Find or create release directory
  console.log("Preparing release environment...");
  const target = options.currentBranch
    ? analysis.context.branch
    : analysis.context.target;

  let releaseDir: string;
  let cleanupNeeded = false;

  if (options.currentBranch) {
    // Release current branch directly (for hotfix branches)
    console.log(`  Releasing current branch: ${target}`);
    const status = await exec("git status --porcelain");
    if (status) {
      console.error("❌ Working directory is dirty. Commit or stash changes first.");
      process.exit(1);
    }
    releaseDir = process.cwd();
  } else {
    releaseDir = await createReleaseWorktree(target, analysis.context.repo, version);
    cleanupNeeded = true;
  }

  try {
    // 7. Update CHANGELOG.md (unless --no-changelog)
    if (!options.noChangelog) {
      console.log("\nUpdating CHANGELOG.md...");

      // Check if CHANGELOG.md would be ignored by .gitignore
      try {
        const ignored = await exec(`git -C "${releaseDir}" check-ignore CHANGELOG.md`);
        if (ignored) {
          console.error("❌ CHANGELOG.md is ignored by .gitignore");
          console.error("   Remove the pattern from .gitignore (check for 'changelog.md' on case-insensitive systems)");
          process.exit(1);
        }
      } catch {
        // check-ignore exits non-zero when file is NOT ignored - that's what we want
      }

      await updateChangelog(releaseDir, version, analysis.changelog);
      await exec(`git -C "${releaseDir}" add CHANGELOG.md`);
    }

    // 8. Commit and tag
    console.log("Creating release commit and tag...");
    if (!options.noChangelog) {
      await exec(
        `git -C "${releaseDir}" commit -m "release: ${version}

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"`
      );
    }
    await exec(`git -C "${releaseDir}" tag "${version}"`);

    // 9. Push
    console.log("Pushing to remote...");
    await exec(`git -C "${releaseDir}" push origin HEAD:${target} --tags`);

    // 10. Create GitHub release
    console.log("Creating GitHub release...");
    // Write notes to temp file to avoid shell escaping issues
    const notesFile = join(releaseDir, ".release-notes.tmp");
    await Bun.write(notesFile, analysis.changelog);
    try {
      await exec(
        `cd "${releaseDir}" && gh release create "${version}" --title "${version}" --notes-file "${notesFile}"`
      );
    } finally {
      try { unlinkSync(notesFile); } catch { /* ignore */ }
    }

    console.log(`\n✅ Released ${version}`);
    console.log(`   https://github.com/${analysis.context.repo}/releases/tag/${version}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`\n❌ Release failed: ${message}`);
    console.error("\nSee references/troubleshooting.md for recovery steps.\n");
    process.exit(1);
  } finally {
    // 11. Cleanup ephemeral worktree
    if (cleanupNeeded) {
      console.log("Cleaning up ephemeral worktree...");
      try {
        await exec(`git worktree remove "${releaseDir}" --force`);
      } catch {
        console.warn(`  Warning: Could not remove ${releaseDir}`);
      }
    }
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
