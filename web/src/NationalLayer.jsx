import { useEffect } from "react";
import L from "leaflet";
import { decodeTile, queryPrediction } from "./national";
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
    let index, config;
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
        "Display center only; not a surveyed boundary.",
        "National candidates are not BARC predictions.",
      ]) {
        const el = document.createElement("span");
        el.textContent = text;
        box.appendChild(el);
      }
      return box;
    };
    async function read(tile) {
      if (cache.has(tile.path)) return cache.get(tile.path);
      const response = await fetch("/national/" + tile.path, {
        signal: abort.signal,
      });
      if (!response.ok) throw Error(`Tile HTTP ${response.status}`);
      let bytes = await response.arrayBuffer();
      if (new Uint8Array(bytes)[0] !== 78) {
        const stream = new Blob([bytes])
          .stream()
          .pipeThrough(new DecompressionStream("gzip"));
        bytes = await new Response(stream).arrayBuffer();
      }
      const points = decodeTile(bytes, tile, index.tile_zoom);
      cache.set(tile.path, points);
      if (cache.size > 24) cache.delete(cache.keys().next().value);
      return points;
    }
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
      if (z < 11) {
        for (const tile of index.tiles) {
          const n = tile.year_counts[year];
          if (!n || !bounds.contains(tile.center)) continue;
          L.circleMarker(tile.center, {
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
      const size = 2 ** index.tile_zoom;
      const visible = index.tiles.filter((t) => {
        const west = (t.x / size) * 360 - 180,
          east = ((t.x + 1) / size) * 360 - 180,
          north =
            (Math.atan(Math.sinh(Math.PI * (1 - (2 * t.y) / size))) * 180) /
            Math.PI,
          south =
            (Math.atan(Math.sinh(Math.PI * (1 - (2 * (t.y + 1)) / size))) *
              180) /
            Math.PI;
        return bounds.intersects([
          [south, west],
          [north, east],
        ]);
      });
      onStatus("Loading national candidates…");
      try {
        const arrays = await Promise.all(visible.map(read));
        if (closed || ticket !== generation) return;
        const eligible = arrays.flatMap((points) =>
          points.filter(
            (field) =>
              field.flags & bit && bounds.contains([field.lat, field.lng]),
          ),
        );
        if (eligible.length > 12000) {
          const cells = new Map();
          for (const field of eligible) {
            const p = map.latLngToContainerPoint([field.lat, field.lng]);
            const key = `${Math.floor(p.x / 48)}:${Math.floor(p.y / 48)}`;
            const cell = cells.get(key) || { lat: 0, lng: 0, n: 0 };
            cell.lat += field.lat;
            cell.lng += field.lng;
            cell.n++;
            cells.set(key, cell);
          }
          for (const cell of cells.values()) {
            const center = [cell.lat / cell.n, cell.lng / cell.n];
            L.circleMarker(center, {
              renderer,
              pane: "national",
              radius: Math.min(10, 2 + Math.log10(cell.n) * 2),
              color: "#fff",
              fillColor: "#fff",
              fillOpacity: 0.5,
              weight: 1,
            })
              .bindTooltip(
                `${cell.n} candidate objects · zoom in for individual IDs`,
              )
              .on("click", () => map.setView(center, map.getZoom() + 2))
              .addTo(group);
          }
          onStatus(
            `${eligible.length.toLocaleString()} candidate objects in counted clusters · zoom in`,
          );
          return;
        }
        let count = 0;
        for (const points of arrays)
          for (const field of points) {
            if (
              !(field.flags & bit) ||
              !bounds.contains([field.lat, field.lng])
            )
              continue;
            count++;
            const marker = L.circleMarker([field.lat, field.lng], {
              renderer,
              pane: "national",
              radius: 2.2,
              color: "#fff",
              weight: 0.6,
              fillColor: "#fff",
              fillOpacity: 0.65,
            }).bindTooltip(tooltip(field), {
              className: "field-hover",
              sticky: true,
            });
            marker
              .on("mouseover", async () => {
                marker.setStyle({ radius: 4, fillOpacity: 1 });
                try {
                  const result = await queryPrediction(
                    field,
                    year,
                    role,
                    { ...config, source_revision: index.source_commit },
                    abort.signal,
                  );
                  if (!closed) marker.setTooltipContent(tooltip(field, result));
                } catch (e) {
                  if (e.name !== "AbortError")
                    marker.setTooltipContent(
                      tooltip(
                        field,
                        null,
                        "Prediction loading failed: " + e.message,
                      ),
                    );
                }
              })
              .on("mouseout", () =>
                marker.setStyle({ radius: 2.2, fillOpacity: 0.65 }),
              )
              .on("click", async () => {
                marker.openTooltip();
                try {
                  const result = await queryPrediction(
                    field,
                    year,
                    role,
                    { ...config, source_revision: index.source_commit },
                    abort.signal,
                  );
                  if (!closed) marker.setTooltipContent(tooltip(field, result));
                } catch (e) {
                  if (e.name !== "AbortError")
                    marker.setTooltipContent(
                      tooltip(
                        field,
                        null,
                        "Prediction loading failed: " + e.message,
                      ),
                    );
                }
              })
              .addTo(group);
          }
        onStatus(
          `${count.toLocaleString()} visible candidate objects · predictions ${config?.endpoint ? "connected" : "not configured"}`,
        );
      } catch (e) {
        if (e.name !== "AbortError" && !closed)
          onStatus("National layer loading failed: " + e.message);
      }
    }
    const schedule = () => {
      clearTimeout(timer);
      timer = setTimeout(draw, 180);
    };
    Promise.all([
      fetch("/national/index.json", { signal: abort.signal }).then((r) => {
        if (!r.ok) throw Error(`Index HTTP ${r.status}`);
        return r.json();
      }),
      fetch("/national/prediction-config.json", { signal: abort.signal }).then(
        (r) => (r.ok ? r.json() : {}),
      ),
    ])
      .then(([i, c]) => {
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
