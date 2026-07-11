#!/usr/bin/env bun
/**
 * Log Outcome Script
 *
 * Logs dependency update outcomes for learning.
 *
 * Usage:
 *   bun ~/.claude/skills/update-dependencies/scripts/log-outcome.ts
 *   bun ~/.claude/skills/update-dependencies/scripts/log-outcome.ts --outcome success --notes "patch security fix"
 *   bun ~/.claude/skills/update-dependencies/scripts/log-outcome.ts --show
 */

import { appendFileSync, existsSync, readFileSync } from "fs";
import { basename } from "path";
import { homedir } from "os";

interface OutcomeEntry {
  date: string;
  project: string;
  ecosystem: string;
  packages: string[];
  from: string;
  to: string;
  risk_score: number;
  outcome: "success" | "failed" | "required_migration";
  notes: string;
}

const DATA_FILE = `${homedir()}/.claude/skills/update-dependencies/data/outcomes.jsonl`;

function detectEcosystem(): string {
  const lockfiles: [string, string][] = [
    ["bun.lock", "bun"],
    ["bun.lockb", "bun"],
    ["pnpm-lock.yaml", "pnpm"],
    ["package-lock.json", "npm"],
    ["uv.lock", "uv"],
    ["poetry.lock", "poetry"],
    ["Cargo.lock", "cargo"],
  ];

  for (const [file, ecosystem] of lockfiles) {
    if (existsSync(file)) return ecosystem;
  }
  return "unknown";
}

function getProjectName(): string {
  return basename(process.cwd());
}

function showHistory(packageFilter?: string) {
  if (!existsSync(DATA_FILE)) {
    console.log("No outcome history yet.");
    return;
  }

  const lines = readFileSync(DATA_FILE, "utf-8").trim().split("\n").filter(Boolean);
  const entries: OutcomeEntry[] = lines.map((line) => JSON.parse(line));

  const filtered = packageFilter
    ? entries.filter((e) => e.packages.some((p) => p.includes(packageFilter)))
    : entries;

  if (filtered.length === 0) {
    console.log(packageFilter ? `No history for packages matching "${packageFilter}"` : "No history.");
    return;
  }

  console.log("# Outcome History\n");
  console.log("| Date | Project | Packages | Outcome | Notes |");
  console.log("|------|---------|----------|---------|-------|");

  for (const entry of filtered.slice(-20)) {
    const pkgs = entry.packages.slice(0, 3).join(", ") + (entry.packages.length > 3 ? "..." : "");
    console.log(`| ${entry.date} | ${entry.project} | ${pkgs} | ${entry.outcome} | ${entry.notes} |`);
  }
}

function logOutcome(entry: OutcomeEntry) {
  const line = JSON.stringify(entry);
  appendFileSync(DATA_FILE, line + "\n");
  console.log("Outcome logged:");
  console.log(line);
}

function printUsage() {
  console.log(`
Usage:
  bun log-outcome.ts --show [package]           Show history (optionally filtered)
  bun log-outcome.ts --packages "a,b" --from "1.0" --to "2.0" --risk 3 --outcome success --notes "worked"

Required for logging:
  --packages   Comma-separated package names
  --from       Version before update
  --to         Version after update
  --risk       Risk score (1-5)
  --outcome    success | failed | required_migration
  --notes      Brief description

Example:
  bun log-outcome.ts --packages "vitest,vite" --from "2.1.0" --to "2.1.8" --risk 2 --outcome success --notes "patch security fix"
`);
}

function main() {
  const args = process.argv.slice(2);

  // Show history
  if (args.includes("--show")) {
    const idx = args.indexOf("--show");
    const packageFilter = args[idx + 1] && !args[idx + 1].startsWith("--") ? args[idx + 1] : undefined;
    showHistory(packageFilter);
    return;
  }

  // Parse arguments
  const getArg = (name: string): string | undefined => {
    const idx = args.indexOf(name);
    return idx !== -1 ? args[idx + 1] : undefined;
  };

  const packages = getArg("--packages");
  const from = getArg("--from");
  const to = getArg("--to");
  const risk = getArg("--risk");
  const outcome = getArg("--outcome") as OutcomeEntry["outcome"];
  const notes = getArg("--notes");

  if (!packages || !outcome) {
    printUsage();

    // Show pre-filled template
    console.log("\n# Pre-filled template:\n");
    console.log(`Project: ${getProjectName()}`);
    console.log(`Ecosystem: ${detectEcosystem()}`);
    console.log(`Date: ${new Date().toISOString().split("T")[0]}`);
    console.log("\nFill in and run:");
    console.log(`bun ~/.claude/skills/update-dependencies/scripts/log-outcome.ts \\
  --packages "pkg1,pkg2" \\
  --from "1.0.0" \\
  --to "2.0.0" \\
  --risk 3 \\
  --outcome success \\
  --notes "brief description"`);
    return;
  }

  const entry: OutcomeEntry = {
    date: new Date().toISOString().split("T")[0],
    project: getProjectName(),
    ecosystem: detectEcosystem(),
    packages: packages.split(",").map((p) => p.trim()),
    from: from || "unknown",
    to: to || "unknown",
    risk_score: parseInt(risk || "3", 10),
    outcome,
    notes: notes || "",
  };

  logOutcome(entry);
}

main();
