import { test } from "node:test";
import assert from "node:assert/strict";
import {
  fieldSnapshot,
  countiesInView,
  FIELD_MIN_ZOOM,
} from "../src/map-data.js";
const field = { properties: { field_id: "barc_001", area_ha: 2.5 } };
test("hover lookup preserves field ID and isolates year and prediction role, including zero probability", () => {
  const rows = [
    {
      field_id: "barc_001",
      year: "2021",
      prediction_role: "oof",
      p_silage: "0",
      predicted_label: "grain",
    },
    {
      field_id: "barc_001",
      year: "2021",
      prediction_role: "inference",
      p_silage: ".8",
      predicted_label: "silage",
    },
    {
      field_id: "barc_001",
      year: "2022",
      prediction_role: "oof",
      p_silage: ".6",
      predicted_label: "silage",
    },
  ];
  const data = {
    "model/predictions.csv": rows,
    "satellite/features.csv": [
      { field_id: "barc_001", year: "2021", quality_flag: "limited" },
    ],
  };
  const info = fieldSnapshot(field, data, 2021, "oof");
  assert.equal(info.field_id, "barc_001");
  assert.equal(info.p_silage, 0);
  assert.equal(info.quality_flag, "limited");
  assert.equal(fieldSnapshot(field, data, 2021, "inference").p_silage, 0.8);
  assert.equal(fieldSnapshot(field, data, 2022, "oof").p_silage, 0.6);
  const missing = fieldSnapshot(field, data, 2023, "oof");
  assert.equal(missing.p_silage, null);
  assert.equal(missing.predicted_label, null);
  assert.equal(missing.quality_flag, null);
  assert.equal(FIELD_MIN_ZOOM, 13);
});
test("county viewport filtering keeps intersecting boundaries without altering source features", () => {
  const features = [
    { bbox: [-77, 38, -76, 40], properties: { GEOID: "24033" } },
    { bbox: [-123, 37, -121, 39], properties: { GEOID: "06001" } },
  ];
  const result = countiesInView(features, {
    west: -76.9,
    south: 39,
    east: -76.8,
    north: 39.1,
  });
  assert.equal(result.length, 1);
  assert.equal(result[0], features[0]);
  assert.equal(result[0].properties.GEOID, "24033");
});
