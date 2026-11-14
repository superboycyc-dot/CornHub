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
