import { test } from "node:test";
import assert from "node:assert/strict";
import { predictionKey, queryPrediction, decodeTile } from "../src/national.js";
test("national IDs preserve leading zeros and source namespaces", () => {
  const bytes = new ArrayBuffer(22),
    v = new DataView(bytes);
  new Uint8Array(bytes).set([78, 70, 68, 49]);
  v.setUint32(4, 1, true);
  v.setBigUint64(8, 123n, true);
  v.setUint8(20, 9);
  v.setUint8(21, 5);
  const [p] = decodeTile(bytes, { x: 30, y: 40 }, 7);
  assert.equal(p.candidate_id, "csb_00123");
  assert.equal(p.geometry_valid, true);
  assert.notEqual(
    predictionKey({
      ...p,
      year: 2021,
      prediction_role: "oof",
      model_version: "a",
    }),
    predictionKey({
      ...p,
      year: 2022,
      prediction_role: "oof",
      model_version: "a",
    }),
  );
});
test("unconfigured prediction slots stay empty; mismatched responses fail", async () => {
  const field = {
    candidate_id: "csb_00123",
    source_dataset_id: "csb_corn_2021_2023",
  };
  assert.equal(await queryPrediction(field, 2021, "oof", {}), null);
  const prior = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({
      ok: true,
      json: async () => ({
        predictions: [
          {
            ...field,
            year: 2022,
            prediction_role: "oof",
            model_version: "v1",
            p_silage: 0.2,
            predicted_label: "grain",
          },
        ],
      }),
    });
    await assert.rejects(
      queryPrediction(field, 2021, "oof", {
        endpoint: "/test",
        model_version: "v1",
      }),
      /mismatch/,
    );
  } finally {
    globalThis.fetch = prior;
  }
});
