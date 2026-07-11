#!/usr/bin/env bun
/**
 * Dependency Analysis Script
 *
 * Detects ecosystem and gathers dependency information.
 *
 * Usage:
 *   bun ~/.claude/skills/update-dependencies/scripts/analyze.ts
 *   bun ~/.claude/skills/update-dependencies/scripts/analyze.ts --security-only
 *   bun ~/.claude/skills/update-dependencies/scripts/analyze.ts --json
 */

import { $ } from "bun";
import { existsSync } from "fs";

type Ecosystem = "npm" | "bun" | "pnpm" | "uv" | "poetry" | "cargo" | "unknown";

interface Vulnerability {
  name: string;
  severity: "critical" | "high" | "moderate" | "low";
  fixAvailable: boolean;
}

interface OutdatedPackage {
  name: string;
  current: string;
  latest: string;
  type: "patch" | "minor" | "major";
}

interface AnalysisResult {
  ecosystem: Ecosystem;
  security: {
    critical: Vulnerability[];
    high: Vulnerability[];
    moderate: Vulnerability[];
    low: Vulnerability[];
    total: number;
  };
  outdated: {
    major: OutdatedPackage[];
    minor: OutdatedPackage[];
    patch: OutdatedPackage[];
    total: number;
  };
}

function detectEcosystem(): Ecosystem {
  const lockfiles: [string, Ecosystem][] = [
    ["bun.lock", "bun"],
    ["bun.lockb", "bun"],
    ["pnpm-lock.yaml", "pnpm"],
    ["package-lock.json", "npm"],
    ["uv.lock", "uv"],
    ["poetry.lock", "poetry"],
    ["Cargo.lock", "cargo"],
  ];

  for (const [file, ecosystem] of lockfiles) {
    if (existsSync(file)) {
      return ecosystem;
    }
  }
  return "unknown";
}

function classifyVersionBump(
  current: string,
  latest: string
): "patch" | "minor" | "major" {
  const clean = (v: string) => v.split("-")[0].replace(/^[~^>=<]+/, "");
  const curParts = clean(current).split(".").map(Number);
  const latParts = clean(latest).split(".").map(Number);

  const [curMajor = 0, curMinor = 0] = curParts;
  const [latMajor = 0, latMinor = 0] = latParts;

  if (latMajor > curMajor) return "major";
  if (latMinor > curMinor) return "minor";
  return "patch";
}

async function getNpmAudit(): Promise<AnalysisResult["security"]> {
  try {
    const result = await $`npm audit --json`.quiet().nothrow();
    const audit = JSON.parse(result.stdout.toString() || "{}");
    const vulnerabilities = audit.vulnerabilities || {};

    const categorized = {
      critical: [] as Vulnerability[],
      high: [] as Vulnerability[],
      moderate: [] as Vulnerability[],
      low: [] as Vulnerability[],
      total: 0,
    };

    for (const [name, data] of Object.entries(vulnerabilities)) {
      const vuln = data as { severity: string; fixAvailable: boolean };
      const severity = vuln.severity as Vulnerability["severity"];

      if (["critical", "high", "moderate", "low"].includes(severity)) {
        categorized[severity].push({
          name,
          severity,
          fixAvailable: vuln.fixAvailable || false,
        });
        categorized.total++;
      }
    }
    return categorized;
  } catch {
    return { critical: [], high: [], moderate: [], low: [], total: 0 };
  }
}

async function getNpmOutdated(): Promise<AnalysisResult["outdated"]> {
  try {
    const result = await $`npm outdated --json`.quiet().nothrow();
    const outdated = JSON.parse(result.stdout.toString() || "{}");

    const categorized = {
      major: [] as OutdatedPackage[],
      minor: [] as OutdatedPackage[],
      patch: [] as OutdatedPackage[],
      total: 0,
    };

    for (const [name, data] of Object.entries(outdated)) {
      const pkg = data as { current: string; latest: string };
      if (!pkg.current || !pkg.latest) continue;

      const type = classifyVersionBump(pkg.current, pkg.latest);
      categorized[type].push({
        name,
        current: pkg.current,
        latest: pkg.latest,
        type,
      });
      categorized.total++;
    }
    return categorized;
  } catch {
    return { major: [], minor: [], patch: [], total: 0 };
  }
}

async function getPythonAudit(): Promise<AnalysisResult["security"]> {
  try {
    const result = await $`pip-audit --format json`.quiet().nothrow();
    const audits = JSON.parse(result.stdout.toString() || "[]");

    const categorized = {
      critical: [] as Vulnerability[],
      high: [] as Vulnerability[],
      moderate: [] as Vulnerability[],
      low: [] as Vulnerability[],
      total: 0,
    };

    for (const vuln of audits) {
      // pip-audit doesn't always have severity, default to moderate
      const severity = "moderate" as Vulnerability["severity"];
      categorized[severity].push({
        name: vuln.name || "unknown",
        severity,
        fixAvailable: !!vuln.fix_versions?.length,
      });
      categorized.total++;
    }
    return categorized;
  } catch {
    return { critical: [], high: [], moderate: [], low: [], total: 0 };
  }
}

async function getPythonOutdated(): Promise<AnalysisResult["outdated"]> {
  try {
    const result = await $`pip list --outdated --format json`.quiet().nothrow();
    const outdated = JSON.parse(result.stdout.toString() || "[]");

    const categorized = {
      major: [] as OutdatedPackage[],
      minor: [] as OutdatedPackage[],
      patch: [] as OutdatedPackage[],
      total: 0,
    };

    for (const pkg of outdated) {
      const type = classifyVersionBump(pkg.version, pkg.latest_version);
      categorized[type].push({
        name: pkg.name,
        current: pkg.version,
        latest: pkg.latest_version,
        type,
      });
      categorized.total++;
    }
    return categorized;
  } catch {
    return { major: [], minor: [], patch: [], total: 0 };
  }
}

async function getCargoAudit(): Promise<AnalysisResult["security"]> {
  try {
    const result = await $`cargo audit --json`.quiet().nothrow();
    const audit = JSON.parse(result.stdout.toString() || "{}");

    const categorized = {
      critical: [] as Vulnerability[],
      high: [] as Vulnerability[],
      moderate: [] as Vulnerability[],
      low: [] as Vulnerability[],
      total: 0,
    };

    for (const vuln of audit.vulnerabilities?.list || []) {
      const severity = "high" as Vulnerability["severity"]; // cargo audit doesn't categorize well
      categorized[severity].push({
        name: vuln.package?.name || "unknown",
        severity,
        fixAvailable: !!vuln.versions?.patched?.length,
      });
      categorized.total++;
    }
    return categorized;
  } catch {
    return { critical: [], high: [], moderate: [], low: [], total: 0 };
  }
}

async function getCargoOutdated(): Promise<AnalysisResult["outdated"]> {
  try {
    const result = await $`cargo outdated --format json`.quiet().nothrow();
    const outdated = JSON.parse(result.stdout.toString() || "{}");

    const categorized = {
      major: [] as OutdatedPackage[],
      minor: [] as OutdatedPackage[],
      patch: [] as OutdatedPackage[],
      total: 0,
    };

    for (const pkg of outdated.dependencies || []) {
      if (!pkg.project || !pkg.latest) continue;
      const type = classifyVersionBump(pkg.project, pkg.latest);
      categorized[type].push({
        name: pkg.name,
        current: pkg.project,
        latest: pkg.latest,
        type,
      });
      categorized.total++;
    }
    return categorized;
  } catch {
    return { major: [], minor: [], patch: [], total: 0 };
  }
}

async function analyze(ecosystem: Ecosystem, securityOnly: boolean): Promise<AnalysisResult> {
  let security: AnalysisResult["security"] = { critical: [], high: [], moderate: [], low: [], total: 0 };
  let outdated: AnalysisResult["outdated"] = { major: [], minor: [], patch: [], total: 0 };

  switch (ecosystem) {
    case "npm":
    case "bun":
    case "pnpm":
      security = await getNpmAudit();
      if (!securityOnly) outdated = await getNpmOutdated();
      break;
    case "uv":
    case "poetry":
      security = await getPythonAudit();
      if (!securityOnly) outdated = await getPythonOutdated();
      break;
    case "cargo":
      security = await getCargoAudit();
      if (!securityOnly) outdated = await getCargoOutdated();
      break;
  }

  return { ecosystem, security, outdated };
}

function printResult(result: AnalysisResult, securityOnly: boolean) {
  console.log("# Dependency Analysis\n");
  console.log(`Ecosystem: **${result.ecosystem}**\n`);

  console.log("## Security Vulnerabilities\n");
  if (result.security.total === 0) {
    console.log("No vulnerabilities found\n");
  } else {
    console.log(`Found ${result.security.total} vulnerabilities:\n`);
    if (result.security.critical.length)
      console.log(`- Critical: ${result.security.critical.length}`);
    if (result.security.high.length)
      console.log(`- High: ${result.security.high.length}`);
    if (result.security.moderate.length)
      console.log(`- Moderate: ${result.security.moderate.length}`);
    if (result.security.low.length)
      console.log(`- Low: ${result.security.low.length}`);
    console.log();
  }

  if (!securityOnly) {
    console.log("## Outdated Packages\n");
    if (result.outdated.total === 0) {
      console.log("All packages up to date\n");
    } else {
      console.log(`Found ${result.outdated.total} outdated packages:\n`);
      if (result.outdated.major.length) {
        console.log(`### Major (${result.outdated.major.length})`);
        result.outdated.major.forEach((p) =>
          console.log(`- ${p.name}: ${p.current} → ${p.latest}`)
        );
        console.log();
      }
      if (result.outdated.minor.length) {
        console.log(`### Minor (${result.outdated.minor.length})`);
        result.outdated.minor.forEach((p) =>
          console.log(`- ${p.name}: ${p.current} → ${p.latest}`)
        );
        console.log();
      }
      if (result.outdated.patch.length) {
        console.log(`### Patch (${result.outdated.patch.length})`);
        result.outdated.patch.forEach((p) =>
          console.log(`- ${p.name}: ${p.current} → ${p.latest}`)
        );
        console.log();
      }
    }
  }
}

async function main() {
  const args = process.argv.slice(2);
  const securityOnly = args.includes("--security-only");
  const jsonOutput = args.includes("--json");

  const ecosystem = detectEcosystem();

  if (ecosystem === "unknown") {
    console.error("Could not detect ecosystem. No lockfile found.");
    process.exit(1);
  }

  const result = await analyze(ecosystem, securityOnly);

  if (jsonOutput) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    printResult(result, securityOnly);
  }
}

main().catch(console.error);
