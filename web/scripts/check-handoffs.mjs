// Verify the files actually published by sync:data. Never trains models or computes D's summaries.
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
import { parse, validate, contractPaths, optionalPaths } from "../src/data.js";
const exec = promisify(execFile);
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const directory = path.join(root, "web/public/data");
const manifest = JSON.parse(
  await fs.readFile(path.join(directory, "manifest.json"), "utf8"),
);
const data = {},
  files = {};
for (const name of [...contractPaths, ...optionalPaths]) {
  if (manifest.files[name]?.status !== "available") {
    assert.ok(
      !contractPaths.includes(name),
      `Required file is not available: ${name}`,
    );
    continue;
  }
  const content = await fs.readFile(path.join(directory, name));
  data[name] = validate(name, parse(name, content.toString("utf8")));
  const source = manifest.files[name].source;
  if (source?.startsWith("git:")) {
    const [, commit, ...parts] = source.split(":");
    const { stdout } = await exec(
      "git",
      ["show", `${commit}:${parts.join(":")}`],
      { cwd: root, encoding: "buffer", maxBuffer: 20 * 1024 * 1024 },
    );
    assert.deepEqual(content, stdout, `Publication bytes differ: ${name}`);
  }
  files[name] = {
    source,
    sha256: createHash("sha256").update(content).digest("hex"),
    rows: Array.isArray(data[name])
      ? data[name].length
      : (data[name].features?.length ?? "object"),
  };
}
const fields = data["core/fields.geojson"].features;
const ids = new Set(fields.map((f) => f.properties.field_id));
const labels = data["core/labels.csv"],
  features = data["satellite/features.csv"],
  predictions = data["model/predictions.csv"];
const key = (row) => JSON.stringify([row.field_id, String(row.year)]);
const labeled = new Set(labels.map(key)),
  featureKeys = new Set(features.map(key));
assert.deepEqual(
  featureKeys,
  labeled,
  "Features do not cover exactly the labeled field-years",
);
const folds = new Map(
  data["core/validation_folds.csv"].map((row) => [key(row), row.fold_id]),
);
for (const [name, rows] of Object.entries(data))
  if (Array.isArray(rows))
    for (const row of rows)
      if (row.field_id)
        assert.ok(
          ids.has(row.field_id),
          `Unknown field in ${name}: ${row.field_id}`,
        );
const roles = {};
for (const role of ["oof", "inference"]) {
  const rows = predictions.filter((row) => row.prediction_role === role);
  assert.deepEqual(
    new Set(rows.map(key)),
    labeled,
    `${role} coverage differs from labels`,
  );
  roles[role] = rows.length;
  for (const row of rows) {
    assert.notEqual(row.p_silage, "");
    assert.equal(
      row.predicted_label,
      Number(row.p_silage) >= 0.5 ? "silage" : "grain",
    );
    if (role === "oof") assert.equal(row.fold_id, folds.get(key(row)));
    else assert.equal(row.fold_id, "");
  }
}
const metrics = data["model/metrics.json"];
assert.equal(metrics.prediction_role, "oof");
assert.equal(metrics.status, "evaluated");
assert.equal(metrics.n_evaluated, roles.oof);
const period = data["analysis/period_status.json"];
for (const input of period?.source_inputs || []) {
  const name = input.path.replace(/^data\/processed\//, "");
  if (files[name] && input.sha256)
    assert.equal(
      files[name].sha256,
      input.sha256,
      `D's input differs from the website: ${name}`,
    );
}
const annual = {};
for (const year of [2022, 2023, 2024, 2025]) {
  const base = `analysis/${year}/oof/`,
    summary = data[base + "summary.json"];
  assert.ok(summary, `Annual summary missing: ${year}`);
  assert.equal(summary.year, year);
  assert.equal(summary.prediction_role, "oof");
  const scope = summary.scope.field_ids;
  assert.equal(new Set(scope).size, scope.length);
  scope.forEach((id) => assert.ok(ids.has(id)));
  for (const name of ["review_queue.csv", "data_needed.csv"])
    for (const row of data[base + name] || []) {
      assert.equal(String(row.year), String(year));
      assert.equal(row.prediction_role, "oof");
      assert.ok(scope.includes(row.field_id));
    }
  if (year > 2023) {
    assert.equal(summary.status, "pending");
    assert.equal(summary.total_area_ha, null);
    assert.equal(summary.expected_silage_area_ha, null);
    assert.equal(summary.coverage_fraction, null);
    assert.equal(scope.length, 0);
  }
  const simulation = data[base + "review_simulation.json"];
  if (simulation?.status === "evaluated")
    assert.equal(simulation.n_evaluated, scope.length);
  annual[year] = {
    status: summary.status,
    cohort: summary.scope.cohort,
    n_selected: scope.length,
    queue_rows: data[base + "review_queue.csv"].length,
    simulation_status: simulation?.status ?? "missing",
  };
}
const quality = {};
features.forEach((row) => {
  quality[row.quality_flag] = (quality[row.quality_flag] || 0) + 1;
});
assert.ok(
  features
    .filter((row) => row.year === "2021")
    .every((row) => row.quality_flag === "limited"),
);
const report = {
  status: "verified",
  verified_at_utc: new Date().toISOString(),
  boundary_count: fields.length,
  labeled_field_count: new Set(labels.map((r) => r.field_id)).size,
  label_year_count: labels.length,
  feature_rows: features.length,
  timeseries_rows: data["satellite/timeseries.csv"].length,
  prediction_roles: roles,
  quality_counts: quality,
  annual,
  files,
  browser_verification:
    "Not performed: supported browser control tool is unavailable.",
};
await fs.writeFile(
  path.join(root, "reports/e_web/handoff-verification.json"),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(
  JSON.stringify(
    {
      ...report,
      files: `${Object.keys(files).length} files verified against source bytes`,
    },
    null,
    2,
  ),
);
