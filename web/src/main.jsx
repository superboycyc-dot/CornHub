import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./style.css";
import { loadData, number, present } from "./data";
const show = (v, missing = "Missing data") =>
  present(v) ? String(v) : missing;
function Icon({ name, size = 18 }) {
  const paths = {
    layers: (
      <>
        <path d="m12 3 9 5-9 5-9-5 9-5Z" />
        <path d="m3 12 9 5 9-5M3 16l9 5 9-5" />
      </>
    ),
    field: (
      <>
        <path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4" />
        <path d="M8 8h8v8H8z" />
      </>
    ),
    chart: (
      <>
        <path d="M4 4v16h16" />
        <path d="m7 14 4-5 4 3 5-7" />
      </>
    ),
    analysis: (
      <>
        <path d="M5 20V11M12 20V4M19 20V8" />
      </>
    ),
    review: (
      <>
        <path d="M9 6h11M9 12h11M9 18h11" />
        <path d="m3 6 1 1 2-2M3 12h2M3 18h2" />
      </>
    ),
    data: (
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0" />
      </>
    ),
    close: <path d="m6 6 12 12M6 18 18 6" />,
    refresh: (
      <>
        <path d="M20 7v5h-5M4 17v-5h5" />
        <path d="M6 7a7 7 0 0 1 11-2l3 3M4 16l3 3a7 7 0 0 0 11-2" />
      </>
    ),
    fit: (
      <>
        <path d="M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    fullscreen: <path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5" />,
    plus: <path d="M12 5v14M5 12h14" />,
    minus: <path d="M5 12h14" />,
    arrow: <path d="m8 5 7 7-7 7" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.field}
    </svg>
  );
}
function Map({ fields, onSelect, selected, controller }) {
  const el = useRef(),
    map = useRef(),
    fitted = useRef();
  const [tileError, setTileError] = useState(false);
  useEffect(() => {
    map.current = L.map(el.current, {
      zoomControl: false,
      scrollWheelZoom: true,
      attributionControl: true,
    }).setView([39, -77], 9);
    controller.current = map.current;
    const basemap = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 19,
        attribution:
          "Imagery © Esri, Maxar, Earthstar Geographics, GIS User Community",
      },
    ).addTo(map.current);
    basemap.on("tileerror", () => setTileError(true));
    const observer = new ResizeObserver(() => map.current?.invalidateSize());
    observer.observe(el.current);
    return () => {
      observer.disconnect();
      map.current.remove();
      controller.current = null;
    };
  }, []);
  useEffect(() => {
    if (!fields?.features.length) return;
    const layer = L.geoJSON(fields, {
      style: (f) => ({
        color: f.properties.field_id === selected ? "#dcff92" : "#c8d4c3",
        weight: f.properties.field_id === selected ? 2.5 : 1,
        fillOpacity: f.properties.field_id === selected ? 0.2 : 0.04,
      }),
      onEachFeature: (f, l) => {
        l.bindTooltip(String(f.properties.field_id));
        l.on("click", () => onSelect(f.properties.field_id));
      },
    }).addTo(map.current);
    if (fitted.current !== fields) {
      map.current.fitBounds(layer.getBounds(), { padding: [80, 80] });
      fitted.current = fields;
    }
    return () => layer.remove();
  }, [fields, selected]);
  return (
    <div className="map-wrap">
      <div ref={el} className="map" aria-label="Field map" />
      <div className="map-vignette" />
      {tileError && (
        <div className="tile-error" role="status">
          Some basemap tiles could not load. Field data remains available in the
          panels.
        </div>
      )}
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
  const [panel, setPanel] = useState(null),
    [fullscreen, setFullscreen] = useState(false),
    [uiNotice, setUiNotice] = useState("");
  const mapController = useRef();
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") setPanel(null);
    };
    const onFullscreen = () =>
      setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("keydown", onKey);
    document.addEventListener("fullscreenchange", onFullscreen);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("fullscreenchange", onFullscreen);
    };
  }, []);
  const tabs = [
    { id: "field", label: "Field", icon: "field" },
    { id: "observations", label: "Observations", icon: "chart" },
    { id: "analysis", label: "Analysis", icon: "analysis" },
    { id: "review", label: "Review", icon: "review" },
    { id: "data", label: "Data status", icon: "data" },
  ];
  const loadedCount = Object.keys(d).length;
  const fitMap = () => {
    if (!mapController.current) return;
    if (fields?.features.length)
      mapController.current.fitBounds(L.geoJSON(fields).getBounds(), {
        padding: [90, 90],
      });
    else mapController.current.setView([39, -77], 9);
  };
  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.documentElement.requestFullscreen)
        await document.documentElement.requestFullscreen();
      else throw Error();
    } catch {
      setUiNotice(
        "Fullscreen is unavailable here. The map already fills this window.",
      );
    }
  };
  const gaps = allIds
    .map((field_id) => {
      const match = (r) => r.field_id === field_id && String(r.year) === year;
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
    .filter((r) => r.reason);
  return (
    <main className="mission" aria-label="CornHub field operations">
      <Map
        fields={fields}
        selected={fieldId}
        onSelect={setId}
        controller={mapController}
      />
      <header className="topbar">
        <a
          className="brand"
          href="#"
          aria-label="CornHub home"
          onClick={(e) => {
            e.preventDefault();
            setPanel(null);
          }}
        >
          CORN<span>HUB</span>
          <i />
        </a>
        <div className="header-divider" />
        <span className="mission-name">FIELD OPERATIONS</span>
        <div className="header-actions">
          <span className="archive-label">BARC / ARCHIVE 2021—2023</span>
          <button
            className="icon-button"
            onClick={reload}
            aria-label="Reload data"
            title="Reload data"
          >
            <Icon name="refresh" />
          </button>
          <button
            className="icon-button fullscreen-button"
            onClick={toggleFullscreen}
            aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            title="Fullscreen"
          >
            <Icon name="fullscreen" />
          </button>
        </div>
      </header>
      <div className="mission-heading">
        <div className="eyebrow">
          <span className="status-dot" /> EARTH OBSERVATION
        </div>
        <h1>
          FIELD
          <br />
          INTELLIGENCE
        </h1>
        <p>Every field. Every observation. In context.</p>
      </div>
      <section className="selectors" aria-label="Map filters">
        <label>
          <span>YEAR</span>
          <select
            aria-label="Year"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          >
            {["2021", "2022", "2023"].map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
        </label>
        <label className="role-select">
          <span>PREDICTION ROLE</span>
          <select
            aria-label="Prediction role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="oof">OOF · Validation</option>
            <option value="inference">Inference</option>
          </select>
        </label>
        <label className="field-select">
          <span>FIELD</span>
          <select
            aria-label="Field"
            value={fieldId}
            disabled={!allIds.length}
            onChange={(e) => setId(e.target.value)}
          >
            {!allIds.length && <option value="">Awaiting fields</option>}
            {allIds.map((i) => (
              <option key={i}>{i}</option>
            ))}
          </select>
        </label>
      </section>
      {!panel && (
        <div className="context-note">
          <span className="crosshair-mark">+</span>
          <div>
            <span className="micro-label">
              {fields?.features.length
                ? "VERIFIED FIELD LAYER"
                : "FIELD LAYER PENDING"}
            </span>
            <p>
              {fields?.features.length
                ? "Select a field to inspect its evidence."
                : "Field boundaries have not been provided"}
            </p>
            <small>
              {fields?.features.length
                ? "Source: core/fields.geojson"
                : "Regional basemap only. No field boundaries are inferred."}
            </small>
          </div>
        </div>
      )}
      <div className="map-tools" aria-label="Map controls">
        <span className="north-marker">
          N<span>↑</span>
        </span>
        <button
          className="icon-button"
          aria-label="Zoom in"
          onClick={() => mapController.current?.zoomIn()}
        >
          <Icon name="plus" />
        </button>
        <button
          className="icon-button"
          aria-label="Zoom out"
          onClick={() => mapController.current?.zoomOut()}
        >
          <Icon name="minus" />
        </button>
        <button
          className="icon-button"
          aria-label="Fit map to fields"
          onClick={fitMap}
        >
          <Icon name="fit" />
        </button>
      </div>
      {panel && (
        <aside
          className="floating-panel"
          aria-label={tabs.find((t) => t.id === panel)?.label + " panel"}
        >
          <div className="panel-header">
            <div>
              <span className="micro-label">
                {year} / {role.toUpperCase()}
              </span>
              <h2>{tabs.find((t) => t.id === panel)?.label}</h2>
            </div>
            <button
              className="icon-button"
              aria-label="Close panel"
              onClick={() => setPanel(null)}
            >
              <Icon name="close" />
            </button>
          </div>
          <div className="panel-content" key={panel}>
            {panel === "field" && (
              <>
                <span className="section-kicker">SELECTED FIELD</span>
                <h3>{fieldId || "Awaiting the shared sample"}</h3>
                <dl>
                  {Object.entries({
                    Year: year,
                    "Area (ha)": show(boundary?.area_ha),
                    "Official ID": show(boundary?.source_field_id),
                    Label: show(label?.label),
                    "Source dataset": show(boundary?.source_dataset_id),
                  }).map(([k, v]) => (
                    <React.Fragment key={k}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </React.Fragment>
                  ))}
                </dl>
                <div className="panel-rule" />
                <span className="section-kicker">MODEL OUTPUT</span>
                <div className="probability-value">
                  {show(prediction?.p_silage, "Not computed")}
                </div>
                <p className="metric-caption">Model silage probability</p>
                <dl>
                  {Object.entries({
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
                  {role === "oof"
                    ? "OOF: predictions from models trained without this field."
                    : "Inference: predictions from the full-data model."}{" "}
                  Model probability is not accuracy.
                </p>
                <small>
                  Source: core/fields.geojson, core/labels.csv,
                  model/predictions.csv
                </small>
              </>
            )}
            {panel === "observations" && (
              <>
                <span className="section-kicker">VEGETATION SIGNAL</span>
                <h3>NDVI time series</h3>
                <Curve rows={selected(d["satellite/timeseries.csv"])} />
                <div className="panel-rule" />
                <span className="section-kicker">OBSERVATION QUALITY</span>
                <h3>Satellite data quality</h3>
                <dl>
                  {[
                    "quality_flag",
                    "valid_obs_count",
                    "max_gap_days",
                    "missing_reason",
                  ].map((k) => (
                    <React.Fragment key={k}>
                      <dt>{k.replaceAll("_", " ")}</dt>
                      <dd>{show(feature?.[k])}</dd>
                    </React.Fragment>
                  ))}
                </dl>
                <p className="notice">
                  Quality describes the satellite data, not the reliability of a
                  model prediction.
                </p>
                <small>
                  Source: satellite/features.csv · Provisional contract quality
                  rules.
                </small>
              </>
            )}
            {panel === "analysis" && (
              <>
                <span className="section-kicker">SELECTED SCOPE ONLY</span>
                <h3>Area and economic summary</h3>
                {summaryMatches ? (
                  <>
                    <p className="summary-status">
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
                          <dt>{k.replaceAll("_", " ")}</dt>
                          <dd>
                            {show(
                              typeof summary[k] === "object" &&
                                summary[k] !== null
                                ? JSON.stringify(summary[k])
                                : summary[k],
                              "Not computed",
                            )}
                          </dd>
                        </React.Fragment>
                      ))}
                    </dl>
                    <p>
                      Economic scenario:{" "}
                      {summary.economic_scenario
                        ? JSON.stringify(summary.economic_scenario)
                        : "Not computed"}
                    </p>
                    {summary.notes && <p>{JSON.stringify(summary.notes)}</p>}
                  </>
                ) : (
                  <p className="empty">
                    Not computed: no summary.json matches the selected year and
                    role. This page does not calculate its own summary.
                  </p>
                )}
                <small>
                  Source: analysis/summary.json · Results supplied by D.
                </small>
                <div className="panel-rule" />
                <span className="section-kicker">EVALUATION</span>
                <h3>Model validation</h3>
                {metrics?.status === "evaluated" &&
                metrics.prediction_role === role ? (
                  <pre>{JSON.stringify(metrics, null, 2)}</pre>
                ) : (
                  <p className="empty">
                    Not computed: no evaluated metrics match the selected
                    prediction role.
                  </p>
                )}
              </>
            )}
            {panel === "review" && (
              <>
                <span className="section-kicker">HUMAN REVIEW</span>
                <h3>Review queue</h3>
                <p>
                  Heuristic priority, not an error probability or economic
                  value.
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
                <small>
                  Source: analysis/review_queue.csv · Original order supplied by
                  D.
                </small>
                <div className="panel-rule" />
                <h3>Data gaps</h3>
                <Table
                  rows={gaps}
                  cols={["field_id", "year", "prediction_role", "reason"]}
                />
              </>
            )}
            {panel === "data" && (
              <>
                <span className="section-kicker">SOURCE READINESS</span>
                <h3>File status and loading errors</h3>
                <p className="source-count">
                  <strong>{loadedCount}</strong>
                  <span>/ 10 contract files loaded</span>
                </p>
                {Object.entries(errors).map(([name, e]) => (
                  <div className="file-status" key={name}>
                    <code>{name}</code>
                    <span>{e}</span>
                  </div>
                ))}
                {!Object.keys(errors).length && (
                  <p>All contract files have been loaded.</p>
                )}
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
                <div className="panel-rule" />
                <small>
                  Contract: docs/team-contract.md
                  <br />
                  Boundaries: A · Time series: B · Model: C · Analysis: D<br />
                  Esri imagery is a contextual basemap, not the team's measured
                  satellite time series.
                </small>
              </>
            )}
          </div>
        </aside>
      )}
      {uiNotice && (
        <div className="ui-notice" role="status">
          {uiNotice}
          <button
            className="icon-button"
            aria-label="Dismiss notice"
            onClick={() => setUiNotice("")}
          >
            <Icon name="close" />
          </button>
        </div>
      )}
      <footer className="flight-deck">
        <div className="flight-id">
          <span className="micro-label">MISSION / BARC</span>
          <div>
            <span className="status-dot amber" />
            {loading
              ? "LOADING DATA"
              : loadedCount === 10
                ? "CONTRACT FILES READY"
                : "AWAITING EVIDENCE"}
          </div>
        </div>
        <nav className="panel-nav" aria-label="Evidence panels">
          {tabs.map((t) => (
            <button
              key={t.id}
              aria-label={t.label}
              aria-pressed={panel === t.id}
              className={panel === t.id ? "active" : ""}
              onClick={() => setPanel(panel === t.id ? null : t.id)}
            >
              <Icon name={t.icon} />
              <span>{t.label}</span>
            </button>
          ))}
        </nav>
        <div className="view-label">
          <Icon name="layers" />
          <div>
            <span className="micro-label">MAP LAYER</span>
            <span>SATELLITE IMAGERY</span>
          </div>
        </div>
      </footer>
      <div className="telemetry">
        <span>
          EPSG:4326 <i /> LONGITUDE / LATITUDE
        </span>
        <span>
          {year} / {role.toUpperCase()} <i />{" "}
          {fields?.features.length
            ? "FIELD BOUNDARIES AVAILABLE"
            : "NO VERIFIED FIELD LAYER"}
        </span>
        <span>
          MODEL:{" "}
          {present(prediction?.p_silage)
            ? "PREDICTION AVAILABLE"
            : "NOT COMPUTED"}
        </span>
      </div>
    </main>
  );
}
createRoot(document.getElementById("root")).render(<App />);
