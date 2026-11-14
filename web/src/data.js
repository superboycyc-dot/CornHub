import Papa from "papaparse";
export const paths = [
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
export function parse(name, text) {
  if (!name.endsWith(".csv")) return JSON.parse(text);
  const result = Papa.parse(text, { header: true, skipEmptyLines: "greedy" });
  const headers = {
    "core/labels.csv": [
      "field_id",
      "year",
      "label",
      "label_raw",
      "source_dataset_id",
    ],
    "core/validation_folds.csv": ["field_id", "year", "fold_id"],
    "satellite/timeseries.csv": [
      "field_id",
      "year",
      "date",
      "sensor",
      "scene_id",
      "ndvi",
      "valid_pixel_fraction",
      "source_dataset_id",
    ],
    "satellite/features.csv": [
      "field_id",
      "year",
      "ndvi_peak",
      "peak_doy",
      "max_drop_per_day",
      "drop_doy",
      "ndvi_late_mean",
      "valid_obs_count",
      "max_gap_days",
      "quality_flag",
      "missing_reason",
    ],
    "model/predictions.csv": [
      "field_id",
      "year",
      "p_silage",
      "predicted_label",
      "prediction_role",
      "fold_id",
      "model_version",
    ],
    "analysis/review_queue.csv": [
      "field_id",
      "year",
      "prediction_role",
      "rank",
      "review_score",
      "reason",
    ],
  };
  for (const key of headers[name] || [])
    if (!result.meta.fields?.includes(key))
      throw Error(`Missing contract field ${key}`);
  if (result.errors.length)
    throw Error(result.errors.map((e) => e.message).join("; "));
  return result.data;
}
export const present = (v) => v !== null && v !== undefined && v !== "";
export const number = (v) =>
  present(v) && Number.isFinite(Number(v)) ? Number(v) : null;
export function unique(rows, keys) {
  const seen = new Set();
  for (const row of rows) {
    const key = JSON.stringify(keys.map((k) => row[k]));
    if (seen.has(key)) throw Error(`Duplicate key ${keys.join("+")}: ${key}`);
    seen.add(key);
  }
  return rows;
}
export function validate(name, data) {
  const keys = {
    "core/labels.csv": ["field_id", "year"],
    "core/validation_folds.csv": ["field_id", "year"],
    "satellite/features.csv": ["field_id", "year"],
    "satellite/timeseries.csv": ["field_id", "year", "date", "scene_id"],
    "model/predictions.csv": ["field_id", "year", "prediction_role"],
    "analysis/review_queue.csv": ["field_id", "year", "prediction_role"],
  };
  if (keys[name]) {
    unique(data, keys[name]);
    for (const row of data) {
      if (!row.field_id || !/^\d{4}$/.test(row.year))
        throw Error("field_id/year does not meet the contract");
      if (
        "prediction_role" in row &&
        !["oof", "inference"].includes(row.prediction_role)
      )
        throw Error("Unknown prediction_role");
      for (const [k, min, max] of [
        ["p_silage", 0, 1],
        ["ndvi", -1, 1],
        ["valid_pixel_fraction", 0, 1],
      ])
        if (
          present(row[k]) &&
          (number(row[k]) === null ||
            number(row[k]) < min ||
            number(row[k]) > max)
        )
          throw Error(`${k} out of range`);
    }
  }
  if (name === "core/fields.geojson") {
    if (data.type !== "FeatureCollection" || !Array.isArray(data.features))
      throw Error("Expected a FeatureCollection");
    unique(
      data.features.map((f) => f.properties),
      ["field_id"],
    );
    if (data.crs && !JSON.stringify(data.crs).match(/4326|CRS84/))
      throw Error("Boundaries must use EPSG:4326");
    for (const f of data.features) {
      if (
        typeof f.properties?.field_id !== "string" ||
        !f.properties.field_id ||
        !["Polygon", "MultiPolygon"].includes(f.geometry?.type)
      )
        throw Error("Boundary ID/geometry does not meet the contract");
      const walk = (c) => {
        if (typeof c[0] === "number") {
          if (
            c.length < 2 ||
            !Number.isFinite(c[0]) ||
            !Number.isFinite(c[1]) ||
            Math.abs(c[0]) > 180 ||
            Math.abs(c[1]) > 90
          )
            throw Error("Invalid longitude/latitude range");
        } else c.forEach(walk);
      };
      walk(f.geometry.coordinates);
    }
  }
  return data;
}
export async function loadData() {
  let manifest;
  try {
    const r = await fetch("/data/manifest.json", { cache: "no-store" });
    if (!r.ok) throw Error(`HTTP ${r.status}`);
    manifest = await r.json();
  } catch (e) {
    return {
      data: {},
      errors: {
        manifest: `Manifest loading failed: ${e.message}; ask the site maintainer to run npm run sync:data and republish`,
      },
    };
  }
  const data = {},
    errors = {};
  await Promise.all(
    paths.map(async (name) => {
      if (manifest.files?.[name]?.status !== "available") {
        errors[name] = manifest.files?.[name]?.reason || "Not provided";
        return;
      }
      try {
        const r = await fetch(`/data/${name}`, { cache: "no-store" });
        if (!r.ok) throw Error(`HTTP ${r.status}`);
        data[name] = validate(name, parse(name, await r.text()));
      } catch (e) {
        errors[name] = `Loading failed: ${e.message}`;
      }
    }),
  );
  return { data, errors, manifest };
}
