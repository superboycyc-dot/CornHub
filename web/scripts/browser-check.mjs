// Isolated fixtures only exercise UI joins. They are never published or used for delivery screenshots.
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("http://localhost:5173");
await page.getByText("Field boundaries have not been provided").waitFor();
await page.screenshot({
  path: "../reports/e_web/empty-state.png",
  fullPage: true,
});
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({
  path: "../reports/e_web/empty-state-mobile.png",
  fullPage: true,
});
assert.equal(
  await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
  false,
);
await page.route("**/data/manifest.json", (r) =>
  r.fulfill({ status: 500, body: "failed" }),
);
await page.getByRole("button", { name: "Reload data" }).click();
await page.getByText(/Manifest loading failed/).waitFor();
await page.unroute("**/data/manifest.json");
const bodies = {
  "core/fields.geojson": JSON.stringify({
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {
          field_id: "test_only_001",
          source_field_id: "001",
          source_dataset_id: "isolated_test",
          area_ha: 2,
        },
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [-76, 39],
              [-76.01, 39],
              [-76.01, 39.01],
              [-76, 39],
            ],
          ],
        },
      },
    ],
  }),
  "model/predictions.csv":
    "field_id,year,p_silage,predicted_label,prediction_role,fold_id,model_version\ntest_only_001,2021,0.2,grain,oof,0,test\ntest_only_001,2021,0.8,silage,inference,,test\ntest_only_001,2022,0.9,silage,oof,0,test\n",
  "analysis/summary.json": JSON.stringify({
    status: "evaluated",
    year: 2021,
    prediction_role: "oof",
    scope: "isolated test",
    expected_silage_area_ha: 0.4,
  }),
};
await page.route("**/data/**", (r) => {
  const name = new URL(r.request().url()).pathname.slice("/data/".length);
  if (name === "manifest.json")
    return r.fulfill({
      json: {
        files: Object.fromEntries(
          Object.keys(bodies).map((k) => [k, { status: "available" }]),
        ),
      },
    });
  if (bodies[name]) return r.fulfill({ body: bodies[name] });
  return r.fulfill({ status: 404 });
});
await page.getByRole("button", { name: "Reload data" }).click();
await page
  .getByRole("heading", { name: "test_only_001", exact: true })
  .waitFor();
assert.equal(
  await page
    .locator("dt")
    .filter({ hasText: "Model silage probability" })
    .locator("+ dd")
    .textContent(),
  "0.2",
);
await page.getByLabel("Prediction role").selectOption("inference");
assert.equal(
  await page
    .locator("dt")
    .filter({ hasText: "Model silage probability" })
    .locator("+ dd")
    .textContent(),
  "0.8",
);
await page
  .getByText(/no summary\.json matches the selected year and role/)
  .waitFor();
await page.getByRole("combobox").nth(0).selectOption("2022");
assert.equal(
  await page
    .locator("dt")
    .filter({ hasText: "Model silage probability" })
    .locator("+ dd")
    .textContent(),
  "Not computed",
);
await page.getByLabel("Prediction role").selectOption("oof");
assert.equal(
  await page
    .locator("dt")
    .filter({ hasText: "Model silage probability" })
    .locator("+ dd")
    .textContent(),
  "0.9",
);
bodies["model/predictions.csv"] += "test_only_001,2022,0.9,silage,oof,0,test\n";
await page.getByRole("button", { name: "Reload data" }).click();
await page.getByText(/Loading failed: Duplicate key/).waitFor();
assert.deepEqual(errors, []);
await browser.close();
console.log(
  "PASS: desktop/mobile empty screenshots; manifest failure; year/role joins; summary scope; duplicate rejection; no browser errors.",
);
