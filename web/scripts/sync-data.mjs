import { promises as fs } from "node:fs";
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
export async function sync(source, target) {
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
        files[name] = { status: "available" };
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
  const files = await sync(
    path.join(root, "data/processed"),
    path.join(root, "web/public/data"),
  );
  for (const [name, info] of Object.entries(files))
    console.log(`${info.status}: ${name}`);
}
