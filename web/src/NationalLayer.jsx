import { useEffect } from "react";
import L from "leaflet";
import { queryPrediction, decodePolygons } from "./national";
export default function NationalLayer({
  controller,
  enabled,
  year,
  role,
  onStatus,
}) {
  useEffect(() => {
    if (!enabled) return;
    const map = controller.current;
    if (!map) return;
    const abort = new AbortController();
    let generation = 0,
      closed = false;
    const cache = new Map();
    const group = L.layerGroup().addTo(map);
    if (!map.getPane("national")) map.createPane("national").style.zIndex = 420;
    const renderer = L.canvas({ pane: "national", padding: 0.2 });
    let index, config, polygonIndex;
    let timer;
    const tooltip = (field, result = null, error = null) => {
      const box = document.createElement("div");
      box.className = "field-tooltip-content";
      for (const text of [
        field.candidate_id,
        `Source: ${field.source_dataset_id}`,
        `${year} / ${role} / ${config?.model_version || "model not configured"}`,
        error ||
          `Model silage probability: ${result?.p_silage == null ? "Not computed" : (result.p_silage * 100).toFixed(1) + "%"}`,
        `Source geometry: ${field.geometry_valid ? "valid" : "flagged invalid"}`,
        field.geometry
          ? "Source polygon · simplified for display; not a cadastral survey."
          : "Display center only; zoom in for polygon outlines.",
        "National candidates are not BARC predictions.",
      ]) {
        const el = document.createElement("span");
        el.textContent = text;
        box.appendChild(el);
      }
      return box;
    };
    async function draw() {
      const ticket = ++generation;
      group.clearLayers();
      if (!index) return;
      if (![2021, 2022, 2023].includes(Number(year))) {
        onStatus("No national candidate data for " + year);
        return;
      }
      const bounds = map.getBounds().pad(0.05),
        bit = 1 << (Number(year) - 2021),
        z = map.getZoom();
      if (z >= 12) {
        onStatus("Loading national field outlines…");
        try {
          const visible = polygonIndex.tiles.filter((t) =>
            bounds.intersects([
              [t.bbox[1], t.bbox[0]],
              [t.bbox[3], t.bbox[2]],
            ]),
          );
          const chunks = await Promise.all(
            visible.map(async (tile) => {
              const key = "polygon:" + tile.path;
              if (cache.has(key)) return cache.get(key);
              const response = await fetch("/national/" + tile.path, {
                signal: abort.signal,
              });
              if (!response.ok) throw Error(`Polygon HTTP ${response.status}`);
              let bytes = await response.arrayBuffer();
              const { decompress } = await import("brotli/decompress");
              const body = new Uint8Array(bytes);
              const decoded =
                String.fromCharCode(...body.subarray(0, 4)) === "NPG1"
                  ? body
                  : decompress(body);
              const rows = decodePolygons(decoded);
              cache.set(key, rows);
              if (cache.size > 8) cache.delete(cache.keys().next().value);
              return rows;
            }),
          );
          if (closed || ticket !== generation) return;
          let count = 0;
          for (const rows of chunks)
            for (const [id, flags, geometry] of rows) {
              if (!(flags & bit)) continue;
              let west = 180,
                east = -180,
                south = 90,
                north = -90;
              const walk = (c) => {
                if (typeof c[0] === "number") {
                  west = Math.min(west, c[0]);
                  east = Math.max(east, c[0]);
                  south = Math.min(south, c[1]);
                  north = Math.max(north, c[1]);
                } else c.forEach(walk);
              };
              walk(geometry.coordinates);
              if (
                !bounds.intersects([
                  [south, west],
                  [north, east],
                ])
              )
                continue;
              const crop = !!(flags & 16),
                field = {
                  candidate_id: id,
                  source_field_id: id.replace(crop ? "cropsight_" : "csb_", ""),
                  source_dataset_id:
                    (crop ? "cropsight" : "csb") + "_corn_2021_2023",
                  geometry_valid: !!(flags & 8),
                  geometry,
                };
              const normal = {
                color: "#ffffff",
                weight: 1.8,
                opacity: 0.95,
                fillColor: "#ffffff",
                fillOpacity: 0.26,
              };
              L.geoJSON(
                { type: "Feature", geometry, properties: { candidate_id: id } },
                {
                  pane: "national",
                  renderer,
                  style: normal,
                  onEachFeature: (_, layer) => {
                    layer.bindTooltip(tooltip(field), {
                      className: "field-hover",
                      sticky: true,
                    });
                    const load = async () => {
                      try {
                        const result = await queryPrediction(
                          field,
                          year,
                          role,
                          { ...config, source_revision: index.source_commit },
                          abort.signal,
                        );
                        if (!closed)
                          layer.setTooltipContent(tooltip(field, result));
                      } catch (e) {
                        if (e.name !== "AbortError")
                          layer.setTooltipContent(
                            tooltip(
                              field,
                              null,
                              "Prediction loading failed: " + e.message,
                            ),
                          );
                      }
                    };
                    layer.on({
                      mouseover: () => {
                        layer.setStyle({ weight: 2.5, fillOpacity: 0.4 });
                        load();
                      },
                      mouseout: () => layer.setStyle(normal),
                      click: () => {
                        layer.openTooltip();
                        load();
                      },
                    });
                  },
                },
              ).addTo(group);
              count++;
            }
          onStatus(`${count.toLocaleString()} visible white field outlines`);
        } catch (e) {
          if (e.name !== "AbortError" && !closed)
            onStatus("National outlines loading failed: " + e.message);
        }
        return;
      }
      if (z < 12) {
        for (const tile of index.tiles) {
          const n = tile.year_counts[year];
          const size = 512,
            west = (tile.x / size) * 360 - 180,
            east = ((tile.x + 1) / size) * 360 - 180,
            north =
              (Math.atan(Math.sinh(Math.PI * (1 - (2 * tile.y) / size))) *
                180) /
              Math.PI,
            south =
              (Math.atan(Math.sinh(Math.PI * (1 - (2 * (tile.y + 1)) / size))) *
                180) /
              Math.PI;
          if (
            !n ||
            !bounds.intersects([
              [south, west],
              [north, east],
            ])
          )
            continue;
          const inside = map.getBounds().pad(-0.05),
            position = [
              Math.max(
                inside.getSouth(),
                Math.min(inside.getNorth(), tile.center[0]),
              ),
              Math.max(
                inside.getWest(),
                Math.min(inside.getEast(), tile.center[1]),
              ),
            ];
          L.circleMarker(position, {
            renderer,
            pane: "national",
            radius: Math.min(9, 2 + Math.log10(n)),
            color: "#fff",
            weight: 1,
            fillColor: "#fff",
            fillOpacity: 0.35,
          })
            .bindTooltip(
              `${n.toLocaleString()} candidate objects · zoom in for individual IDs`,
            )
            .on("click", () => map.setView(tile.center, 12))
            .addTo(group);
        }
        onStatus("White clusters · zoom in to inspect candidates");
        return;
      }
    }
    const schedule = () => {
      clearTimeout(timer);
      timer = setTimeout(draw, 180);
    };
    Promise.all([
      fetch("/national/polygons-index.json", { signal: abort.signal }).then(
        (r) => {
          if (!r.ok) throw Error(`Polygon index HTTP ${r.status}`);
          return r.json();
        },
      ),
      fetch("/national/overview.json", { signal: abort.signal }).then((r) => {
        if (!r.ok) throw Error(`Index HTTP ${r.status}`);
        return r.json();
      }),
      fetch("/national/prediction-config.json", { signal: abort.signal }).then(
        (r) => (r.ok ? r.json() : {}),
      ),
    ])
      .then(([polygons, i, c]) => {
        polygonIndex = polygons;
        index = i;
        config = c;
        map.attributionControl.addAttribution(
          "Candidates: USDA NASS CSB; CropSight-US / Zhou, Liu & Diao CC-BY-4.0",
        );
        draw();
      })
      .catch((e) => {
        if (e.name !== "AbortError")
          onStatus("National layer loading failed: " + e.message);
      });
    map.on("moveend zoomend", schedule);
    return () => {
      closed = true;
      generation++;
      abort.abort();
      clearTimeout(timer);
      map.off("moveend zoomend", schedule);
      map.removeLayer(group);
      if (map.hasLayer(renderer)) map.removeLayer(renderer);
      map.attributionControl.removeAttribution(
        "Candidates: USDA NASS CSB; CropSight-US / Zhou, Liu & Diao CC-BY-4.0",
      );
    };
  }, [controller, enabled, year, role, onStatus]);
  return null;
}
