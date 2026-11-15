import { promises as fs } from "node:fs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
const execFileAsync = promisify(execFile);
import path from "node:path";
import { fileURLToPath } from "node:url";
export const expected = [
  "core/fields.geojson",
  "core/labels.csv",
  "core/smoke_sample.json",
  "core/validation_folds.csv",
  "satellite/timeseries.csv",
  "satellite/features.csv",
  "model/predictions.csv",
  "model/metrics.json",
  "analysis/summary.json",
  "analysis/review_queue.csv",
];
export async function sync(
  source,
  target,
  { repositoryRoot, handoffs = [] } = {},
) {
  await fs.mkdir(target, { recursive: true });
  const files = {};
  async function copy(dir, relative = "") {
    for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
      const name = path.posix.join(relative, entry.name);
      if (entry.isDirectory()) await copy(path.join(dir, entry.name), name);
      else if (entry.isFile()) {
        const dest = path.join(target, name);
        await fs.mkdir(path.dirname(dest), { recursive: true });
        await fs.copyFile(path.join(dir, entry.name), dest);
        files[name] = { status: "available", source: `data/processed/${name}` };
      }
    }
  }
  // Remove old publication copies, so deleted upstream files cannot survive a sync.
  await fs.rm(target, { recursive: true, force: true });
  await fs.mkdir(target, { recursive: true });
  try {
    await copy(source);
  } catch (e) {
    if (e.code !== "ENOENT") throw e;
  }
  for (const handoff of handoffs) {
    if (!/^[a-f0-9]{40}$/.test(handoff.commit))
      throw Error("Handoff commit must be a full SHA");
    for (const name of handoff.files) {
      if (
        !expected.includes(name) &&
        name !== "analysis/period_status.json" &&
        !/^analysis\/\d{4}\/(oof|inference)\/(summary\.json|review_queue\.csv|data_needed\.csv|review_simulation\.json)$/.test(
          name,
        )
      )
        throw Error(`Unexpected handoff path: ${name}`);
      if (files[name]?.status === "available") continue;
      try {
        const { stdout } = await execFileAsync(
          "git",
          ["show", `${handoff.commit}:data/processed/${name}`],
          {
            cwd: repositoryRoot,
            encoding: "buffer",
            maxBuffer: 20 * 1024 * 1024,
          },
        );
        const dest = path.join(target, name);
        await fs.mkdir(path.dirname(dest), { recursive: true });
        await fs.writeFile(dest, stdout);
        files[name] = {
          status: "available",
          source: `git:${handoff.commit}:data/processed/${name}`,
          role: handoff.role,
        };
      } catch {
        files[name] = {
          status: "missing",
          reason: `Pinned ${handoff.role} handoff not available locally. Fetch origin ${handoff.branch}; no substitute was generated.`,
        };
      }
    }
  }
  for (const name of expected) files[name] ??= { status: "missing" };
  await fs.writeFile(
    path.join(target, "manifest.json"),
    JSON.stringify({ files }, null, 2) + "\n",
  );
  return files;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../..",
  );
  const { handoffs } = JSON.parse(
    await fs.readFile(path.join(root, "web/data-handoffs.json"), "utf8"),
  );
  const files = await sync(
    path.join(root, "data/processed"),
    path.join(root, "web/public/data"),
    { repositoryRoot: root, handoffs },
  );
  const referenceTarget = path.join(root, "web/public/reference");
  await fs.rm(referenceTarget, { recursive: true, force: true });
  try {
    await fs.cp(path.join(root, "web/reference"), referenceTarget, {
      recursive: true,
    });
  } catch (e) {
    if (e.code !== "ENOENT") throw e;
  }
  await fs.rm(path.join(root, "web/public/national"), {
    recursive: true,
    force: true,
  });
  await fs.cp(
    path.join(root, "web/national"),
    path.join(root, "web/public/national"),
    { recursive: true },
  );
  for (const [name, info] of Object.entries(files))
    console.log(`${info.status}: ${name}`);
}
