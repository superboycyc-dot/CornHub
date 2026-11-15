import React, { useEffect, useRef, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import L from "leaflet";
import NationalLayer from "./NationalLayer";
import useV9 from "./useV9";
import {probabilityColor,v9Record,v9Details} from "./v9";
import "leaflet/dist/leaflet.css";
import "./style.css";
import {
  loadData,
  number,
  present,
  contractPaths,
  selectAnalysis,
  selectReviewQueue,
} from "./data";
import { FIELD_MIN_ZOOM, fieldSnapshot, countiesInView } from "./map-data";
// At BARC latitude, zoom 13 with a 100 CSS-pixel metric scale renders 1 km.
const INITIAL_MAP_ZOOM = 13;
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
function fieldTooltip(info, v9row) {
  const root = document.createElement("div");
  root.className = "field-tooltip-content";
  const text = (tag, value, className) => {
    const element = document.createElement(tag);
    element.textContent = value;
    if (className) element.className = className;
    root.appendChild(element);
    return element;
  };
  if(v9row) {
    text("strong",info.field_id,"tooltip-title");
    for(const detail of v9Details(v9row)) text("span",detail,"tooltip-detail");
    text("span","V9 model silage probability colors · baseline outputs are separate in the detail panel.","tooltip-footnote");
    return root;
  }
  text("span", "BARC / VERIFIED FIELD", "tooltip-kicker");
  text("strong", info.field_id, "tooltip-title");
  text(
    "span",
    `${info.year} · ${info.role.toUpperCase()} · ${info.area_ha === null ? "Area missing" : info.area_ha.toFixed(2) + " ha"}`,
    "tooltip-context",
  );
  text("span", "MODEL SILAGE PROBABILITY", "tooltip-kicker");
  text(
    "strong",
    info.p_silage === null
      ? "Not computed"
      : `${(info.p_silage * 100).toFixed(1)}%`,
    "tooltip-probability",
  );
  text(
    "span",
    `Predicted class: ${info.predicted_label || "Not computed"}`,
    "tooltip-detail",
  );
  text(
    "span",
    `Satellite quality: ${info.quality_flag || "Missing data"}`,
    "tooltip-detail",
  );
  text(
    "span",
    "Uncalibrated probability, not accuracy. Click to inspect.",
    "tooltip-footnote",
  );
  return root;
}
function Map({
  fields,
  data,
  year,
  role,
  onSelect,
  selected,
  controller,
  showCounties,
  showFields,
  onZoomChange,
  onCountyStatus,
  v9,
}) {
  const el = useRef(),
    map = useRef(),
    fitted = useRef();
  const [tileError, setTileError] = useState(false),
    [counties, setCounties] = useState(null);
  useEffect(() => {
    const abort = new AbortController();
    fetch("/reference/us-counties.geojson.gz", { signal: abort.signal })
      .then(async (r) => {
        if (!r.ok) throw Error(`HTTP ${r.status}`);
        const bytes = await r.arrayBuffer();
        const text =
          new Uint8Array(bytes)[0] === 31
            ? await new Response(
                new Blob([bytes])
                  .stream()
                  .pipeThrough(new DecompressionStream("gzip")),
              ).text()
            : new TextDecoder().decode(bytes);
        return JSON.parse(text);
      })
      .then((value) => {
        if (
          value.type !== "FeatureCollection" ||
          !Array.isArray(value.features) ||
          value.features.some(
            (f) => !Array.isArray(f.bbox) || f.bbox.length !== 4,
          )
        )
          throw Error("Invalid county layer");
        setCounties(value);
        onCountyStatus("ready");
      })
      .catch((e) => {
        if (e.name !== "AbortError")
          onCountyStatus(`County layer could not load: ${e.message}`);
      });
    return () => abort.abort();
  }, []);
  useEffect(() => {
    map.current = L.map(el.current, {
      zoomControl: false,
      scrollWheelZoom: true,
      attributionControl: true,
    }).setView([39.0234, -76.8751], INITIAL_MAP_ZOOM);
    controller.current = map.current;
    map.current.createPane("county-lines").style.zIndex = 350;
    map.current.createPane("county-labels").style.zIndex = 390;
    map.current.getPane("county-labels").style.pointerEvents = "none";
    map.current.createPane("field-polygons").style.zIndex = 450;
    L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 19,
        attribution:
          "Imagery © Esri, Maxar, Earthstar Geographics, GIS User Community",
      },
    )
      .addTo(map.current)
      .on("tileerror", () => setTileError(true));
    L.control
      .scale({ imperial: false, maxWidth: 100, position: "bottomleft" })
      .addTo(map.current);
    const zoom = () => onZoomChange(map.current.getZoom());
    map.current.on("zoomend", zoom);
    zoom();
    const observer = new ResizeObserver(() => map.current?.invalidateSize());
    observer.observe(el.current);
    return () => {
      observer.disconnect();
      map.current.remove();
      controller.current = null;
    };
  }, []);
  useEffect(() => {
    if (!counties || !showCounties) return;
    const lines = L.layerGroup().addTo(map.current),
      labels = L.layerGroup().addTo(map.current);
    map.current.attributionControl.addAttribution(
      "Counties: U.S. Census Bureau / 2026",
    );
    const redraw = () => {
      lines.clearLayers();
      labels.clearLayers();
      if (map.current.getZoom() < 6) return;
      const viewport = map.current.getBounds().pad(0.12);
      const visible = countiesInView(counties.features, {
        west: viewport.getWest(),
        south: viewport.getSouth(),
        east: viewport.getEast(),
        north: viewport.getNorth(),
      });
      L.geoJSON(
        { type: "FeatureCollection", features: visible },
        {
          pane: "county-lines",
          style: {
            color: "#c2d0dc",
            weight: 1.1,
            opacity: 0.65,
            fillColor: "#d4dce3",
            fillOpacity: 0.015,
            dashArray: "5 6",
          },
          onEachFeature: (feature, layer) => {
            const content = document.createElement("span");
            content.textContent = `${feature.properties.NAME} · Census 2026 · GEOID ${feature.properties.GEOID}`;
            layer.bindTooltip(content, {
              sticky: true,
              className: "county-hover",
            });
          },
        },
      ).addTo(lines);
      if (map.current.getZoom() >= 8)
        visible.slice(0, 80).forEach((feature) => {
          const lat = number(feature.properties.INTPTLAT),
            lng = number(feature.properties.INTPTLON);
          if (lat === null || lng === null || !viewport.contains([lat, lng]))
            return;
          const label = document.createElement("span");
          label.textContent = feature.properties.NAME;
          L.marker([lat, lng], {
            pane: "county-labels",
            interactive: false,
            keyboard: false,
            icon: L.divIcon({
              html: label,
              className: "county-label",
              iconSize: [180, 24],
              iconAnchor: [90, 12],
            }),
          }).addTo(labels);
        });
    };
    map.current.on("moveend zoomend", redraw);
    redraw();
    return () => {
      map.current.off("moveend zoomend", redraw);
      map.current.removeLayer(lines);
      map.current.removeLayer(labels);
      map.current.attributionControl.removeAttribution(
        "Counties: U.S. Census Bureau / 2026",
      );
    };
  }, [counties, showCounties]);
  useEffect(() => {
    if (!fields?.features.length) return;
    const rowFor = feature => v9Record(v9,feature.properties.source_dataset_id,feature.properties.field_id,year,role);
    const normal = (feature) => ({
      color: probabilityColor(rowFor(feature)),
      weight: feature.properties.field_id === selected ? 2.5 : 1.8,
      opacity: 1,
      fillColor: probabilityColor(rowFor(feature)),
      fillOpacity: feature.properties.field_id === selected ? 0.38 : 0.26,
    });
    const layer = L.geoJSON(fields, {
      pane: "field-polygons",
      style: normal,
      onEachFeature: (feature, polygon) => {
        const info = fieldSnapshot(feature, data, year, role);
        polygon.bindTooltip(fieldTooltip(info,rowFor(feature)), {
          sticky: true,
          direction: "top",
          offset: [0, -14],
          className: "field-hover",
          opacity: 1,
        });
        const highlight = () => {
          polygon.setStyle({ ...normal(feature), weight: 3, fillOpacity: 0.52 });
          polygon.bringToFront();
        };
        const reset = () => polygon.setStyle(normal(feature));
        polygon.on({
          mouseover: highlight,
          mouseout: reset,
          click: () => {
            polygon.closeTooltip();
            onSelect(feature.properties.field_id);
          },
          add: () => {
            const path = polygon.getElement();
            if (!path) return;
            path.setAttribute("tabindex", "0");
            path.setAttribute("role", "button");
            path.setAttribute(
              "aria-label",
              `Field ${info.field_id}, ${info.year}, ${info.role}, model silage probability ${info.p_silage === null ? "not computed" : info.p_silage}`,
            );
            path.onfocus = () => {
              highlight();
              polygon.openTooltip(polygon.getBounds().getCenter());
            };
            path.onblur = () => {
              reset();
              polygon.closeTooltip();
            };
            path.onkeydown = (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect(info.field_id);
              }
            };
          },
        });
      },
    });
    const toggle = () => {
      const visible = showFields && map.current.getZoom() >= FIELD_MIN_ZOOM;
      if (visible && !map.current.hasLayer(layer)) layer.addTo(map.current);
      else if (!visible && map.current.hasLayer(layer))
        map.current.removeLayer(layer);
    };
    map.current.on("zoomend", toggle);
    if (fitted.current !== fields) {
      // Use a fixed initial scale rather than viewport-dependent fitBounds.
      // The 1 km ruler is computed by Leaflet from actual map distances.
      map.current.setView(layer.getBounds().getCenter(), INITIAL_MAP_ZOOM, {
        animate: false,
      });
      // Initial focus only: users remain free to zoom out across the United States.
      fitted.current = fields;
    }
    toggle();
    return () => {
      map.current.off("zoomend", toggle);
      if (map.current.hasLayer(layer)) map.current.removeLayer(layer);
    };
  }, [fields, selected, data, year, role, showFields, onSelect, v9]);
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
    [role, setRole] = useState("inference"),
    [id, setId] = useState("");
  const v9 = useV9(year,role);
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
  const selectedV9 = v9Record(v9,boundary?.source_dataset_id,fieldId,year,role);
  const summary = selectAnalysis(d, year, role),
    summaryMatches =
      summary &&
      String(summary.year) === year &&
      summary.prediction_role === role;
  const metrics = d["model/metrics.json"];
  const queue = selectReviewQueue(d, year, role);
  const reviewSimulation = d[`analysis/${year}/${role}/review_simulation.json`];
  const dataNeeded = d[`analysis/${year}/${role}/data_needed.csv`];
  const annualStatus = (d["analysis/period_status.json"]?.years || []).find(
    (row) => String(row.year) === year,
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
  const [nationalEnabled, setNationalEnabled] = useState(true),
    [nationalStatus, setNationalStatus] = useState("");
  const [zoomLevel, setZoomLevel] = useState(9),
    [showCounties, setShowCounties] = useState(true),
    [showFields, setShowFields] = useState(true),
    [countyStatus, setCountyStatus] = useState("loading");
  const selectField = useCallback((value) => {
    setId(value);
    setPanel("field");
  }, []);
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
  const loadedCount = contractPaths.filter((name) => name in d).length;
  const fitMap = () => {
    if (!mapController.current) return;
    if (fields?.features.length) {
      mapController.current.fitBounds(L.geoJSON(fields).getBounds(), {
        padding: [90, 90],
        maxZoom: 15,
      });
      if (mapController.current.getZoom() < FIELD_MIN_ZOOM)
        mapController.current.setZoom(FIELD_MIN_ZOOM);
    } else mapController.current.setView([39.0234, -76.8751], FIELD_MIN_ZOOM);
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
  const annualLabeledIds = (d["core/labels.csv"] || [])
    .filter((row) => String(row.year) === year)
    .map((row) => row.field_id);
  const gaps = annualLabeledIds
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
        onSelect={selectField}
        controller={mapController}
        data={d}
        year={year}
        role={role}
        showCounties={showCounties}
        showFields={showFields}
        onZoomChange={setZoomLevel}
        onCountyStatus={setCountyStatus}
        v9={v9}
      />
      <NationalLayer
        controller={mapController}
        enabled={nationalEnabled}
        year={year}
        role={role}
        onStatus={setNationalStatus}
        v9={v9}
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
            {["2021", "2022", "2023", "2024", "2025"].map((y) => (
              <option key={y} value={y}>
                {Number(y) > 2023 ? `${y} · Pending` : y}
              </option>
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
            onChange={(e) => {
              selectField(e.target.value);
              const feature = fields?.features.find(
                (f) => f.properties.field_id === e.target.value,
              );
              if (feature)
                mapController.current?.flyToBounds(
                  L.geoJSON(feature).getBounds(),
                  { padding: [90, 90], maxZoom: 16 },
                );
            }}
          >
            {!allIds.length && <option value="">Awaiting fields</option>}
            {allIds.map((i) => (
              <option key={i}>{i}</option>
            ))}
          </select>
        </label>
      </section>
      <div className="national-control">
        <label>
          <input
            type="checkbox"
            checked={nationalEnabled}
            onChange={(e) => setNationalEnabled(e.target.checked)}
          />
          <span className="national-swatch" />
          US candidate fields · Maryland outlines
        </label>
        {nationalEnabled && (
          <small role="status">{nationalStatus || "Loading…"}</small>
        )}
        <div className="probability-legend" aria-label="V9 model silage probability legend">
          <span><i style={{background:"#61df8c"}} /> &gt;90%</span>
          <span><i style={{background:"#ffcf45"}} /> &gt;60–90%</span>
          <span><i style={{background:"#ff5b5b"}} /> ≤60%</span>
          <span><i style={{background:"#fff"}} /> Unavailable</span>
        </div>
        <small>MD V9 model silage probability · inference · {year}</small>
        <small role="status">{v9.status==='ready'?v9.message:(v9.message||'Loading V9 probability…')}</small>
      </div>
      <div className="layer-switches" aria-label="Map layers">
        <button
          aria-pressed={showCounties}
          onClick={() => setShowCounties(!showCounties)}
        >
          <span className="layer-swatch counties" />
          Counties <small>2026</small>
        </button>
        <button
          aria-pressed={showFields}
          onClick={() => setShowFields(!showFields)}
        >
          <span className="layer-swatch fields" />
          Fields <small>{fields?.features.length || "pending"}</small>
        </button>
        <span className="zoom-readout">
          Z{zoomLevel} / FIELDS ≥ {FIELD_MIN_ZOOM}
        </span>
      </div>
      {countyStatus !== "ready" && countyStatus !== "loading" && (
        <div className="county-error" role="status">
          {countyStatus}
        </div>
      )}
      {!panel && (
        <div className="context-note">
          <span className="crosshair-mark">+</span>
          <div>
            <span className="micro-label">
              {fields?.features.length
                ? showFields
                  ? "VERIFIED FIELD LAYER"
                  : "FIELD LAYER HIDDEN"
                : "FIELD LAYER PENDING"}
            </span>
            <p>
              {fields?.features.length
                ? !showFields
                  ? "Enable the field layer to inspect boundaries."
                  : zoomLevel < FIELD_MIN_ZOOM
                    ? "Zoom in to reveal verified field boundaries."
                    : "Hover a field for its prediction. Click for details."
                : "Field boundaries have not been provided"}
            </p>
            <small>
              {fields?.features.length
                ? "Maryland / BARC · Zoom out to explore the United States."
                : "Regional basemap only. No field boundaries are inferred."}
            </small>
            {fields?.features.length > 0 &&
              (zoomLevel < FIELD_MIN_ZOOM || !showFields) && (
                <button
                  className="show-fields-button"
                  onClick={() => {
                    setShowFields(true);
                    fitMap();
                  }}
                >
                  Zoom to fields <Icon name="arrow" size={13} />
                </button>
              )}
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
                {Number(year) > 2023 && (
                  <p className="notice">
                    BARC baseline observations and predictions are unavailable for {year}.
                    Any V9 conditional result is shown separately below. Historical
                    boundaries do not verify corn eligibility for this year.
                  </p>
                )}
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
                <span className="section-kicker">V9 INFERENCE / MODEL PROBABILITY COLORS</span>
                {v9Details(selectedV9).map((line,i)=><p className="v9-detail" key={i}>{line}</p>)}
                <div className="panel-rule" />
                <span className="section-kicker">BARC BASELINE MODEL OUTPUT / {role.toUpperCase()}</span>
                <div className="probability-value">
                  {present(prediction?.p_silage)
                    ? String(Number(Number(prediction.p_silage).toFixed(6)))
                    : "Not computed"}
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
                {role === "oof" &&
                  label?.label &&
                  prediction?.predicted_label &&
                  label.label !== prediction.predicted_label && (
                    <p className="notice">
                      This held-out prediction differs from the recorded label (
                      {label.label}). It is a real OOF error; satellite quality
                      does not establish correctness.
                    </p>
                  )}
                <p className="notice">
                  {role === "oof"
                    ? "OOF: predictions from models trained without this field."
                    : "Inference: predictions from the full-data model."}{" "}
                  Model probability is uncalibrated and is not accuracy.
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
                  Source: D's year-specific analysis/{year}/{role}/summary.json,
                  or a matching root summary. Active D summaries cover
                  2022–2025; 2024/2025 are pending.
                </small>
                <div className="panel-rule" />
                <span className="section-kicker">EVALUATION</span>
                <h3>Model validation</h3>
                <p>
                  Pooled OOF evaluation across 2021–2023, not the selected year
                  alone. Probabilities are uncalibrated; results are
                  exploratory.
                </p>
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
                <div className="panel-rule" />
                <span className="section-kicker">OOF REVIEW SIMULATION</span>
                <h3>Same-budget review comparison</h3>
                {reviewSimulation?.status === "evaluated" ? (
                  <>
                    <dl>
                      {[
                        "budget",
                        "n_evaluated",
                        "initial_absolute_error_ha",
                        "heuristic_absolute_error_ha",
                        "random_absolute_error_median_ha",
                        "random_absolute_error_min_ha",
                        "random_absolute_error_max_ha",
                        "random_repeats",
                        "seed",
                      ].map((key) => (
                        <React.Fragment key={key}>
                          <dt>{key.replaceAll("_", " ")}</dt>
                          <dd>{show(reviewSimulation[key])}</dd>
                        </React.Fragment>
                      ))}
                    </dl>
                    <p>
                      Smaller absolute area error is better. Review can increase
                      error; these results do not establish a general ranking
                      benefit.
                    </p>
                    {reviewSimulation.notes && (
                      <p>{JSON.stringify(reviewSimulation.notes)}</p>
                    )}
                  </>
                ) : (
                  <p className="empty">
                    Not evaluated for this year and prediction role.
                  </p>
                )}
                {year === "2021" && role === "oof" && queue.length === 0 && (
                  <p className="notice">
                    The 2021 labeled observations are all limited. No
                    usable-only formal review queue is available under D's
                    current policy; the empty queue does not mean there are no
                    uncertainties.
                  </p>
                )}
                <div className="panel-rule" />
                <h3>Data gaps</h3>
                {Array.isArray(dataNeeded) ? (
                  <Table
                    rows={dataNeeded}
                    cols={[
                      "field_id",
                      "year",
                      "prediction_role",
                      "quality_flag",
                      "missing_reason",
                    ]}
                  />
                ) : (
                  <Table
                    rows={gaps}
                    cols={["field_id", "year", "prediction_role", "reason"]}
                  />
                )}
                {annualStatus?.blockers?.length > 0 && (
                  <p>{JSON.stringify(annualStatus.blockers)}</p>
                )}
              </>
            )}
            {panel === "data" && (
              <>
                <span className="section-kicker">SOURCE READINESS</span>
                <h3>File status and loading errors</h3>
                <dl>
                  <dt>Reference boundaries</dt>
                  <dd>{fields?.features.length ?? "Pending"}</dd>
                  <dt>Fields with labels</dt>
                  <dd>
                    {d["core/labels.csv"]
                      ? new Set(d["core/labels.csv"].map((row) => row.field_id))
                          .size
                      : "Pending"}
                  </dd>
                  <dt>Labeled field-years</dt>
                  <dd>{d["core/labels.csv"]?.length ?? "Pending"}</dd>
                  <dt>Observed scene records</dt>
                  <dd>{d["satellite/timeseries.csv"]?.length ?? "Pending"}</dd>
                </dl>
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
                <details>
                  <summary>Handoff provenance</summary>
                  <pre>
                    {Object.entries(state.manifest?.files || {})
                      .filter(
                        ([name]) =>
                          name.startsWith("core/") ||
                          name.startsWith("satellite/") ||
                          name.startsWith("model/") ||
                          name.startsWith("analysis/"),
                      )
                      .map(
                        ([name, info]) =>
                          `${name}: ${info.source || info.reason || info.status}`,
                      )
                      .join("\n")}
                  </pre>
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
                <div className="panel-rule" />
                <small>
                  Contract: docs/team-contract.md
                  <br />
                  Boundaries: A · Time series: B · Model: C · Analysis: D<br />
                  Esri imagery is a contextual basemap, not the team's measured
                  satellite time series. Counties: U.S. Census Bureau, January
                  2026 vintage. Generalized geographic context, not crop-year
                  statistics or a cadastral survey.
                  <br />
                  <a
                    href="https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/9"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Census county source
                  </a>{" "}
                  ·{" "}
                  <a
                    href="https://doi.org/10.1002/agg2.20474"
                    target="_blank"
                    rel="noreferrer"
                  >
                    BARC reference (Dulaney et al.)
                  </a>{" "}
                  ·{" "}
                  <a
                    href="https://doi.org/10.3390/s23208595"
                    target="_blank"
                    rel="noreferrer"
                  >
                    BARC reference (Kraatz et al.)
                  </a>
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
