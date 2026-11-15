import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { sync, expected } from "./sync-data.mjs";
import { parse, validate, number } from "../src/data.js";
test("sync preserves exact bytes, missing files and upstream deletion", async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), "cornhub-"));
  try {
    const source = path.join(temp, "source"),
      dest = path.join(temp, "dest");
    await mkdir(path.join(source, "core"), { recursive: true });
    const body =
      'field_id,year,label,label_raw,source_dataset_id\r\nbarc_001,2021,grain,"a,b",official\r\n';
    await writeFile(path.join(source, "core/labels.csv"), body);
    await sync(source, dest);
    assert.equal(
      await readFile(path.join(dest, "core/labels.csv"), "utf8"),
      body,
    );
    await rm(source, { recursive: true });
    const manifest = await sync(source, dest);
    assert.equal(manifest["core/labels.csv"].status, "missing");
    assert.equal(Object.keys(manifest).length, expected.length);
    await assert.rejects(readFile(path.join(dest, "core/labels.csv")));
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});
test("CSV preserves leading zeros, quotes and missing values", () => {
  const rows = parse(
    "core/labels.csv",
    'field_id,year,label,label_raw,source_dataset_id\nbarc_001,2021,grain,"a,b",official\n',
  );
  assert.equal(rows[0].field_id, "barc_001");
  assert.equal(rows[0].label_raw, "a,b");
  assert.equal(number(""), null);
  assert.equal(number(null), null);
  assert.equal(number("0"), 0);
});
test("duplicates and invalid probabilities fail visibly; roles remain distinct", () => {
  const row = {
    field_id: "barc_001",
    year: "2021",
    p_silage: "0",
    prediction_role: "oof",
  };
  assert.throws(
    () => validate("model/predictions.csv", [row, row]),
    /Duplicate key/,
  );
  assert.doesNotThrow(() =>
    validate("model/predictions.csv", [
      row,
      { ...row, prediction_role: "inference" },
    ]),
  );
  assert.throws(
    () => validate("model/predictions.csv", [{ ...row, p_silage: "1.1" }]),
    /out of range/,
  );
  assert.throws(
    () =>
      validate("core/fields.geojson", {
        type: "FeatureCollection",
        features: [],
        crs: { name: "EPSG:26918" },
      }),
    /4326/,
  );
});
