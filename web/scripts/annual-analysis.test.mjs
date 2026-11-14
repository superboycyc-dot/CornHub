import { test } from "node:test";
import assert from "node:assert/strict";
import {
  selectAnalysis,
  selectReviewQueue,
  parse,
  validate,
} from "../src/data.js";
test("annual results take precedence and cannot cross years or prediction roles", () => {
  const root = {
    year: 2022,
    prediction_role: "oof",
    expected_silage_area_ha: 1,
  };
  const annual = {
    year: 2023,
    prediction_role: "oof",
    expected_silage_area_ha: 2,
  };
  const data = {
    "analysis/summary.json": root,
    "analysis/2023/oof/summary.json": annual,
  };
  assert.equal(selectAnalysis(data, 2022, "oof"), root);
  assert.equal(selectAnalysis(data, 2023, "oof"), annual);
  assert.equal(selectAnalysis(data, 2021, "oof"), null);
  assert.equal(selectAnalysis(data, 2023, "inference"), null);
  const pending = {
    year: 2024,
    prediction_role: "oof",
    status: "pending",
    total_area_ha: null,
    expected_silage_area_ha: null,
  };
  data["analysis/2024/oof/summary.json"] = pending;
  assert.equal(selectAnalysis(data, 2024, "oof").expected_silage_area_ha, null);
});
test("empty annual review queue never falls back to a different cohort; nested CSVs retain schema checks", () => {
  const row = {
    field_id: "barc_1",
    year: "2022",
    prediction_role: "oof",
    rank: "1",
    review_score: ".1",
    reason: "test",
  };
  const data = {
    "analysis/review_queue.csv": [row],
    "analysis/2024/oof/review_queue.csv": [],
  };
  assert.deepEqual(selectReviewQueue(data, 2024, "oof"), []);
  assert.deepEqual(selectReviewQueue(data, 2022, "inference"), []);
  assert.deepEqual(selectReviewQueue(data, 2022, "oof"), [row]);
  const name = "analysis/2022/oof/review_queue.csv";
  assert.throws(() => parse(name, "field_id,year\n"), /Missing contract field/);
  assert.throws(() => validate(name, [row, row]), /Duplicate key/);
});
