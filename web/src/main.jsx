import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./style.css";
import { loadData, number, present } from "./data";
const show = (v, missing = "Missing data") =>
  present(v) ? String(v) : missing;
function Map({ fields, onSelect, selected }) {
  const el = useRef(),
    map = useRef();
  useEffect(() => {
    map.current = L.map(el.current).setView([0, 0], 2);
    return () => map.current.remove();
  }, []);
  useEffect(() => {
    if (!fields?.features.length) return;
    const layer = L.geoJSON(fields, {
      style: (f) => ({
        color: f.properties.field_id === selected ? "#ffca68" : "#307a64",
        weight: 2,
        fillOpacity: 0.25,
      }),
      onEachFeature: (f, l) => {
        l.bindTooltip(String(f.properties.field_id));
        l.on("click", () => onSelect(f.properties.field_id));
      },
    }).addTo(map.current);
    map.current.fitBounds(layer.getBounds(), { padding: [24, 24] });
    return () => layer.remove();
  }, [fields, selected]);
  return (
    <div className="map-wrap">
      <div ref={el} className="map" aria-label="Field map" />
      {!fields?.features.length && (
        <div className="map-empty">
          Field boundaries have not been provided
          <br />
          <small>Awaiting A: core/fields.geojson · EPSG:4326</small>
        </div>
      )}
      <span className="map-note">
        Longitude, latitude · No external basemap
      </span>
    </div>
  );
}
function Curve({ rows }) {
  const good = rows
    .filter((r) => number(r.ndvi) !== null)
    .sort(
      (a, b) =>
        a.date.localeCompare(b.date) || a.scene_id.localeCompare(b.scene_id),
    );
  if (!good.length)
    return (
      <p className="empty">
        Missing data: no observed NDVI values are available.
      </p>
    );
  const dates = good.map((r) => Date.parse(r.date)),
    min = Math.min(...dates),
    max = Math.max(...dates);
  return (
    <>
      <svg
        viewBox="0 0 640 190"
        role="img"
        aria-label="Observed NDVI points; no interpolation or connecting lines"
      >
        <line x1="40" y1="10" x2="40" y2="165" stroke="#aaa" />
        <line x1="40" y1="165" x2="620" y2="165" stroke="#aaa" />
        {[-1, 0, 1].map((v) => (
          <text key={v} x="4" y={90 - v * 72}>
            {v}
          </text>
        ))}
        {good.map((r, i) => (
          <circle
            key={i}
            cx={50 + ((dates[i] - min) / (max - min || 1)) * 550}
            cy={90 - Number(r.ndvi) * 72}
            r="4"
            fill={number(r.valid_pixel_fraction) >= 0.5 ? "#286c53" : "#a36c31"}
          >
            <title>
              {r.date} NDVI={r.ndvi} valid-pixel fraction=
              {r.valid_pixel_fraction} scene_id=
              {r.scene_id}
            </title>
          </circle>
        ))}
        <text x="40" y="188">
          {good[0].date}
        </text>
        <text x="530" y="188">
          {good.at(-1).date}
        </text>
      </svg>
      <small>
        Observed points only; no interpolation. Brown: valid-pixel fraction
        below 0.5 or missing. Source: satellite/timeseries.csv
      </small>
      <details>
        <summary>Scene-level sources</summary>
        <Table
          rows={rows}
          cols={[
            "date",
            "ndvi",
            "valid_pixel_fraction",
            "sensor",
            "scene_id",
            "source_dataset_id",
          ]}
        />
      </details>
    </>
  );
}
function Table({ rows, cols }) {
  return rows.length ? (
    <div className="scroll">
      <table>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c}>{show(r[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <p className="empty">No records provided</p>
  );
}
function App() {
  const [state, setState] = useState({ data: {}, errors: {} }),
    [loading, setLoading] = useState(true),
    [year, setYear] = useState("2021"),
    [role, setRole] = useState("oof"),
    [id, setId] = useState("");
  const reload = () => {
    setLoading(true);
    loadData().then((s) => {
      setState(s);
      setLoading(false);
    });
  };
  useEffect(reload, []);
  const { data: d, errors } = state,
    fields = d["core/fields.geojson"];
  const allIds = [
    ...new Set([
      ...(fields?.features.map((f) => f.properties.field_id) || []),
      ...Object.values(d)
        .filter(Array.isArray)
        .flat()
        .map((r) => r.field_id)
        .filter(Boolean),
    ]),
  ].sort();
  const fieldId = allIds.includes(id) ? id : allIds[0] || "";
  const selected = (rows) =>
    (rows || []).filter(
      (r) => r.field_id === fieldId && String(r.year) === year,
    );
  const feature = selected(d["satellite/features.csv"])[0],
    prediction = selected(d["model/predictions.csv"]).find(
      (r) => r.prediction_role === role,
    ),
    label = selected(d["core/labels.csv"])[0];
  const boundary = fields?.features.find(
    (f) => f.properties.field_id === fieldId,
  )?.properties;
  const summary = d["analysis/summary.json"],
    summaryMatches =
      summary &&
      String(summary.year) === year &&
      summary.prediction_role === role;
  const metrics = d["model/metrics.json"];
  const queue = (d["analysis/review_queue.csv"] || []).filter(
    (r) => String(r.year) === year && r.prediction_role === role,
  );
  const orphan = Object.entries(d)
    .filter(([, v]) => Array.isArray(v))
    .flatMap(([name, rows]) =>
      rows
        .filter(
          (r) =>
            r.field_id &&
            !fields?.features.some((f) => f.properties.field_id === r.field_id),
        )
        .map((r) => `${name}: ${r.field_id} / ${r.year}`),
    );
  return (
    <>
      <header>
        <div className="brand">
          C<span>●</span>RNHUB
        </div>
        <span>BARC / Field Evidence Workspace</span>
        <span className="stage">Phase 01 · Data integration</span>
      </header>
      <main>
        <div className="intro">
          <div>
            <p className="eyebrow">FIELD EVIDENCE · 2021—2023</p>
            <h1>Explore harvest evidence, field by field.</h1>
            <p>
              Explore satellite observations, model silage probabilities, and
              data quality separately. Results apply only to the selected scope.
            </p>
          </div>
          <button onClick={reload}>Reload data</button>
        </div>
        <div className="toolbar">
          <label>
            Year{" "}
            <select value={year} onChange={(e) => setYear(e.target.value)}>
              {["2021", "2022", "2023"].map((y) => (
                <option key={y}>{y}</option>
              ))}
            </select>
          </label>
          <label>
            Prediction role{" "}
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="oof">oof · Held-out field validation</option>
              <option value="inference">
                inference · Full-model predictions
              </option>
            </select>
          </label>
          <label>
            Field{" "}
            <select value={fieldId} onChange={(e) => setId(e.target.value)}>
              <option value="">Select a field</option>
              {allIds.map((i) => (
                <option key={i}>{i}</option>
              ))}
            </select>
          </label>
          <span>
            {loading ? "Loading…" : "Source: published data/processed snapshot"}
          </span>
        </div>
        <div className="grid">
          <section className="card map-card">
            <h2>
              Field map <small>Observed boundaries</small>
            </h2>
            <Map fields={fields} selected={fieldId} onSelect={setId} />
          </section>
          <section className="card">
            <h2>Field details</h2>
            <h3>{fieldId || "Awaiting the shared sample"}</h3>
            <dl>
              {Object.entries({
                Year: year,
                "Area (ha)": show(boundary?.area_ha),
                "Official ID": show(boundary?.source_field_id),
                Label: show(label?.label),
                "Source dataset": show(boundary?.source_dataset_id),
                "Model silage probability": show(
                  prediction?.p_silage,
                  "Not computed",
                ),
                "Predicted class": show(
                  prediction?.predicted_label,
                  "Not computed",
                ),
                "Model version": show(
                  prediction?.model_version,
                  "Not computed",
                ),
                "Prediction role": role,
              }).map(([k, v]) => (
                <React.Fragment key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </React.Fragment>
              ))}
            </dl>
            <p className="notice">
              Model probability is not accuracy. Missing predictions are shown
              as Not computed. Source: model/predictions.csv.
            </p>
          </section>
          <section className="card">
            <h2>
              NDVI time series <small>{year} · No interpolation</small>
            </h2>
            <Curve rows={selected(d["satellite/timeseries.csv"])} />
          </section>
          <section className="card">
            <h2>Satellite data quality</h2>
            <dl>
              {[
                "quality_flag",
                "valid_obs_count",
                "max_gap_days",
                "missing_reason",
              ].map((k) => (
                <React.Fragment key={k}>
                  <dt>{k}</dt>
                  <dd>{show(feature?.[k])}</dd>
                </React.Fragment>
              ))}
            </dl>
            <small>
              Source: satellite/features.csv · Provisional quality rules do not
              measure prediction reliability.
            </small>
          </section>
          <section className="card">
            <h2>
              Area and economic summary <small>Results supplied by D</small>
            </h2>
            {summaryMatches ? (
              <>
                <p>
                  {summary.status === "pending"
                    ? "Not computed"
                    : summary.status}
                </p>
                <dl>
                  {[
                    "scope",
                    "prediction_role",
                    "total_area_ha",
                    "covered_area_ha",
                    "coverage_fraction",
                    "expected_silage_area_ha",
                    "expected_grain_area_ha",
                  ].map((k) => (
                    <React.Fragment key={k}>
                      <dt>{k}</dt>
                      <dd>
                        {show(
                          typeof summary[k] === "object"
                            ? JSON.stringify(summary[k])
                            : summary[k],
                          "Not computed",
                        )}
                      </dd>
                    </React.Fragment>
                  ))}
                </dl>
                <p>
                  Economic scenario:
                  {summary.economic_scenario
                    ? JSON.stringify(summary.economic_scenario)
                    : "Not computed"}
                </p>
                <p>{JSON.stringify(summary.notes)}</p>
              </>
            ) : (
              <p className="empty">
                Not computed: no summary.json matches the selected year and
                role. This page does not calculate its own summary.
              </p>
            )}
          </section>
          <section className="card">
            <h2>Model validation</h2>
            {metrics?.status === "evaluated" &&
            metrics.prediction_role === role ? (
              <pre>{JSON.stringify(metrics, null, 2)}</pre>
            ) : (
              <p className="empty">
                Not computed: no evaluated metrics match the selected prediction
                role.
              </p>
            )}
          </section>
          <section className="card wide">
            <h2>Review queue</h2>
            <p>
              Source: analysis/review_queue.csv · Heuristic priority, not an
              error probability or economic value.
            </p>
            <Table
              rows={queue}
              cols={[
                "rank",
                "field_id",
                "year",
                "prediction_role",
                "review_score",
                "reason",
              ]}
            />
          </section>
          <section className="card wide">
            <h2>Data gaps and integration checks</h2>
            <Table
              rows={allIds
                .map((field_id) => {
                  const match = (r) =>
                    r.field_id === field_id && String(r.year) === year;
                  const f = (d["satellite/features.csv"] || []).find(match);
                  const p = (d["model/predictions.csv"] || []).find(
                    (r) => match(r) && r.prediction_role === role,
                  );
                  return {
                    field_id,
                    year,
                    prediction_role: role,
                    reason: [
                      !present(p?.p_silage) && "No prediction",
                      (!f || f.quality_flag !== "usable") &&
                        `Satellite quality: ${f?.quality_flag || "Missing data"}`,
                    ]
                      .filter(Boolean)
                      .join("; "),
                  };
                })
                .filter((r) => r.reason)}
              cols={["field_id", "year", "prediction_role", "reason"]}
            />
            <details open>
              <summary>File status and loading errors</summary>
              {Object.entries(errors).map(([name, e]) => (
                <p className="file-status" key={name}>
                  <code>{name}</code>
                  <span>{e}</span>
                </p>
              ))}
              {!Object.keys(errors).length && (
                <p>All contract files have been loaded.</p>
              )}
            </details>
            {!!orphan.length && (
              <details>
                <summary>
                  Records without matching boundaries (retained)
                </summary>
                <pre>{orphan.join("\n")}</pre>
              </details>
            )}
            <details>
              <summary>Input record counts</summary>
              <pre>
                {Object.entries(d)
                  .map(
                    ([k, v]) =>
                      `${k}: ${Array.isArray(v) ? v.length : (v.features?.length ?? "JSON object")}`,
                  )
                  .join("\n")}
              </pre>
            </details>
          </section>
        </div>
        <footer>
          Contract: docs/team-contract.md · Boundaries: A · Time series: B ·
          Model: C · Summary: D · Website: E
        </footer>
      </main>
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
