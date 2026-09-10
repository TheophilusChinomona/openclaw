// Check Workflows tests cover check workflows script behavior.
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { cleanupTempDirs, makeTempDir } from "../helpers/temp-dir.js";

const scriptPath = path.resolve("scripts/check-workflows.mts");
const tempDirs: string[] = [];

afterEach(() => {
  cleanupTempDirs(tempDirs);
});

describe("check-workflows", () => {
  it("prints an actionable diagnostic when actionlint and go are unavailable", () => {
    const result = spawnSync(process.execPath, ["--import", "tsx", scriptPath], {
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: "",
      },
    });

    expect(result.status).toBe(1);
    expect(result.stderr).toContain("missing workflow linter");
    expect(result.stderr).toContain("install actionlint, Go");
    expect(result.stderr).toContain("011a6d15e749bb3f2d771eed9c7aa0e7e3e10ee7");
  });

  it("uses the pinned go fallback and audits all workflows with zizmor", () => {
    const tempDir = makeTempDir(tempDirs, "check-workflows-");
    const binDir = path.join(tempDir, "bin");
    const markerPath = path.join(tempDir, "go-run.txt");
    const preCommitMarkerPath = path.join(tempDir, "pre-commit.txt");
    mkdirSync(binDir);
    writeFileSync(
      path.join(binDir, "go"),
      [
        "#!/bin/sh",
        'if [ "$1" = "version" ]; then exit 0; fi',
        'if [ "$1" = "run" ]; then printf "%s\\n" "$*" > "$GO_FALLBACK_MARKER"; exit 0; fi',
        "exit 1",
        "",
      ].join("\n"),
      { mode: 0o755 },
    );
    writeFileSync(
      path.join(binDir, "pre-commit"),
      [
        "#!/bin/sh",
        'if [ "$1" = "--version" ]; then exit 0; fi',
        'printf "%s\\n" "$*" >> "$PRE_COMMIT_MARKER"',
        "exit 0",
        "",
      ].join("\n"),
      { mode: 0o755 },
    );
    for (const command of ["python3", "node"]) {
      writeFileSync(path.join(binDir, command), "#!/bin/sh\nexit 0\n", { mode: 0o755 });
    }

    const result = spawnSync(process.execPath, ["--import", "tsx", scriptPath], {
      encoding: "utf8",
      env: {
        ...process.env,
        GO_FALLBACK_MARKER: markerPath,
        PRE_COMMIT_MARKER: preCommitMarkerPath,
        PATH: binDir,
      },
    });

    expect(result.status).toBe(0);
    expect(readFileSync(markerPath, "utf8")).toContain(
      "github.com/rhysd/actionlint/cmd/actionlint@011a6d15e749bb3f2d771eed9c7aa0e7e3e10ee7",
    );
    const preCommitArgs = readFileSync(preCommitMarkerPath, "utf8");
    expect(preCommitArgs).toContain("run --config .pre-commit-config.yaml zizmor --files");
    expect(preCommitArgs).toContain(".github/workflows/ci.yml");
  });

  it("bootstraps pinned pre-commit in a temporary Python venv when needed", () => {
    const tempDir = makeTempDir(tempDirs, "check-workflows-");
    const binDir = path.join(tempDir, "bin");
    const markerPath = path.join(tempDir, "python.txt");
    mkdirSync(binDir);
    writeFileSync(path.join(binDir, "node"), "#!/bin/sh\nexit 0\n", { mode: 0o755 });
    writeFileSync(
      path.join(binDir, "python3"),
      [
        "#!/bin/sh",
        'if [ "$1" = "--version" ]; then exit 0; fi',
        'if [ "$1" = "-m" ] && [ "$2" = "pre_commit" ] && [ "$3" = "--version" ]; then exit 1; fi',
        'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then',
        '  printf "%s\\n" "$*" >> "$PRE_COMMIT_BOOTSTRAP_MARKER"',
        "  exit 0",
        "fi",
        'if [ "$1" = "-m" ] && [ "$2" = "pre_commit" ]; then',
        '  printf "%s\\n" "$*" >> "$PRE_COMMIT_BOOTSTRAP_MARKER"',
        "  exit 0",
        "fi",
        'if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then',
        '  /bin/mkdir -p "$3/bin"',
        '  /bin/cp "$0" "$3/bin/python"',
        '  /bin/chmod +x "$3/bin/python"',
        "  exit 0",
        "fi",
        "exit 0",
        "",
      ].join("\n"),
      { mode: 0o755 },
    );

    const result = spawnSync(process.execPath, ["--import", "tsx", scriptPath], {
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: binDir,
        PRE_COMMIT_BOOTSTRAP_MARKER: markerPath,
      },
    });

    expect(result.status).toBe(0);
    const pythonArgs = readFileSync(markerPath, "utf8");
    expect(pythonArgs).toContain("-m pip install --disable-pip-version-check pre-commit==4.6.2");
    expect(pythonArgs).toContain(
      "-m pre_commit run --config .pre-commit-config.yaml actionlint --files",
    );
    expect(pythonArgs).toContain(
      "-m pre_commit run --config .pre-commit-config.yaml zizmor --files",
    );
  });

  it("prints the missing runtime diagnostic when Python venv support is unavailable", () => {
    const tempDir = makeTempDir(tempDirs, "check-workflows-");
    const binDir = path.join(tempDir, "bin");
    mkdirSync(binDir);
    writeFileSync(path.join(binDir, "node"), "#!/bin/sh\nexit 0\n", { mode: 0o755 });
    writeFileSync(
      path.join(binDir, "python3"),
      [
        "#!/bin/sh",
        'if [ "$1" = "--version" ]; then exit 0; fi',
        'if [ "$1" = "-m" ] && [ "$2" = "pre_commit" ] && [ "$3" = "--version" ]; then exit 1; fi',
        'if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then',
        '  printf "%s\\n" "python venv unavailable" >&2',
        "  exit 1",
        "fi",
        "exit 1",
        "",
      ].join("\n"),
      { mode: 0o755 },
    );

    const result = spawnSync(process.execPath, ["--import", "tsx", scriptPath], {
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: binDir,
      },
    });

    expect(result.status).toBe(1);
    expect(result.stderr).toContain("python venv unavailable");
    expect(result.stderr).toContain("missing pre-commit runtime for actionlint");
    expect(result.stderr).toContain("Python venv support for pre-commit 4.6.2");
  });

  it("cleans the temporary Python venv before exiting on hook failure", () => {
    const tempDir = makeTempDir(tempDirs, "check-workflows-");
    const binDir = path.join(tempDir, "bin");
    const markerPath = path.join(tempDir, "venv-path.txt");
    mkdirSync(binDir);
    writeFileSync(path.join(binDir, "node"), "#!/bin/sh\nexit 0\n", { mode: 0o755 });
    writeFileSync(
      path.join(binDir, "python3"),
      [
        "#!/bin/sh",
        'if [ "$1" = "--version" ]; then exit 0; fi',
        'if [ "$1" = "-m" ] && [ "$2" = "pre_commit" ] && [ "$3" = "--version" ]; then exit 1; fi',
        'if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then',
        '  /bin/mkdir -p "$3/bin"',
        '  /bin/cp "$0" "$3/bin/python"',
        '  /bin/chmod +x "$3/bin/python"',
        '  printf "%s\\n" "$3" > "$PRE_COMMIT_VENV_MARKER"',
        "  exit 0",
        "fi",
        'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then exit 0; fi',
        'if [ "$1" = "-m" ] && [ "$2" = "pre_commit" ]; then',
        '  printf "%s\\n" "hook failed" >&2',
        "  exit 13",
        "fi",
        "exit 1",
        "",
      ].join("\n"),
      { mode: 0o755 },
    );

    const result = spawnSync(process.execPath, ["--import", "tsx", scriptPath], {
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: binDir,
        PRE_COMMIT_VENV_MARKER: markerPath,
      },
    });

    expect(result.status).toBe(13);
    expect(result.stderr).toContain("hook failed");
    expect(existsSync(readFileSync(markerPath, "utf8").trim())).toBe(false);
  });
});
