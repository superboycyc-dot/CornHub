import { test } from "node:test";
import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import os from "node:os";
import path from "node:path";
import { sync } from "./sync-data.mjs";
const exec = promisify(execFile);
test("pinned handoff is byte-exact, local output wins, unavailable commits cannot leave stale copies", async () => {
  const repo = await fs.mkdtemp(path.join(os.tmpdir(), "cornhub-handoff-"));
  try {
    const git = (...args) => exec("git", args, { cwd: repo });
    await git("init", "-b", "test");
    await fs.mkdir(path.join(repo, "data/processed/core"), { recursive: true });
    const body =
      "field_id,year,label,label_raw,source_dataset_id\r\nbarc_1,2021,grain,Grain,isolated_test\r\n";
    await fs.writeFile(path.join(repo, "data/processed/core/labels.csv"), body);
    await git("add", "data");
    await git(
      "-c",
      "user.name=Isolated Test",
      "-c",
      "user.email=test@example.invalid",
      "commit",
      "-m",
      "test",
    );
    const { stdout } = await git("rev-parse", "HEAD");
    const commit = stdout.trim();
    const local = path.join(repo, "local"),
      dest = path.join(repo, "publish");
    const handoff = {
      role: "A",
      commit,
      branch: "work/a-data",
      files: ["core/labels.csv"],
    };
    let result = await sync(local, dest, {
      repositoryRoot: repo,
      handoffs: [handoff],
    });
    assert.equal(
      await fs.readFile(path.join(dest, "core/labels.csv"), "utf8"),
      body,
    );
    assert.equal(
      result["core/labels.csv"].source,
      `git:${commit}:data/processed/core/labels.csv`,
    );
    await fs.mkdir(path.join(local, "core"), { recursive: true });
    await fs.writeFile(path.join(local, "core/labels.csv"), body + "\r\n");
    result = await sync(local, dest, {
      repositoryRoot: repo,
      handoffs: [handoff],
    });
    assert.equal(
      await fs.readFile(path.join(dest, "core/labels.csv"), "utf8"),
      body + "\r\n",
    );
    assert.equal(
      result["core/labels.csv"].source,
      "data/processed/core/labels.csv",
    );
    await fs.rm(local, { recursive: true });
    result = await sync(local, dest, {
      repositoryRoot: repo,
      handoffs: [{ ...handoff, commit: "0".repeat(40) }],
    });
    assert.equal(result["core/labels.csv"].status, "missing");
    await assert.rejects(fs.readFile(path.join(dest, "core/labels.csv")));
  } finally {
    await fs.rm(repo, { recursive: true, force: true });
  }
});

test("national candidates stay out of BARC publication, including stale copies", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "cornhub-scope-"));
  try {
    const source = path.join(root, "source"), target = path.join(root, "target");
    await fs.mkdir(path.join(source, "external_corn/csb"), { recursive: true });
    await fs.mkdir(path.join(source, "core"), { recursive: true });
    await fs.mkdir(path.join(target, "external_corn"), { recursive: true });
    await fs.writeFile(path.join(source, "external_corn/csb/part.parquet"), "research only");
    await fs.writeFile(path.join(target, "external_corn/stale.parquet"), "stale");
    await fs.writeFile(path.join(source, "core/labels.csv"), "field_id,year,label\n");
    const files = await sync(source, target);
    assert.equal(files["core/labels.csv"].status, "available");
    assert.ok(!Object.keys(files).some((name) => name.startsWith("external_corn/")));
    await assert.rejects(fs.stat(path.join(target, "external_corn")), { code: "ENOENT" });
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
