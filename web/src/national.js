export function predictionKey(p) {
  return JSON.stringify([
    p.source_dataset_id,
    p.candidate_id,
    Number(p.year),
    p.prediction_role,
    p.model_version,
  ]);
}
export async function queryPrediction(field, year, role, config, signal) {
  if (!config?.endpoint || !config.model_version) return null;
  const request = {
    source_revision: config.source_revision,
    source_dataset_id: field.source_dataset_id,
    candidate_id: field.candidate_id,
    year: Number(year),
    prediction_role: role,
    model_version: config.model_version,
  };
  const response = await fetch(config.endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...request, candidate_ids: [field.candidate_id] }),
    signal,
    credentials: "omit",
  });
  if (!response.ok) throw Error(`Prediction HTTP ${response.status}`);
  const payload = await response.json();
  if (!Array.isArray(payload.predictions))
    throw Error("Invalid prediction response");
  for (const row of payload.predictions) {
    if (predictionKey(row) !== predictionKey(request))
      throw Error("Prediction identity/year/role/version mismatch");
    if (row.p_silage === null) continue;
    if (
      typeof row.p_silage !== "number" ||
      !Number.isFinite(row.p_silage) ||
      row.p_silage < 0 ||
      row.p_silage > 1
    )
      throw Error("Invalid model probability");
    if (row.predicted_label !== (row.p_silage >= 0.5 ? "silage" : "grain"))
      throw Error("Prediction class mismatch");
  }
  if (payload.predictions.length > 1) throw Error("Duplicate prediction");
  return payload.predictions[0] || null;
}
export function decodeTile(buffer, tile, zoom) {
  const view = new DataView(buffer);
  if (String.fromCharCode(...new Uint8Array(buffer, 0, 4)) !== "NFD1")
    throw Error("Invalid national tile");
  const count = view.getUint32(4, true);
  if (buffer.byteLength !== 8 + count * 14)
    throw Error("Truncated national tile");
  const points = [];
  for (let i = 0; i < count; i++) {
    const o = 8 + i * 14,
      id = view
        .getBigUint64(o, true)
        .toString()
        .padStart(view.getUint8(o + 13), "0"),
      flags = view.getUint8(o + 12),
      crop = !!(flags & 16);
    const x = (tile.x + view.getUint16(o + 8, true) / 65535) / 2 ** zoom,
      y = (tile.y + view.getUint16(o + 10, true) / 65535) / 2 ** zoom;
    points.push({
      candidate_id: (crop ? "cropsight_" : "csb_") + id,
      source_field_id: id,
      source_dataset_id: (crop ? "cropsight" : "csb") + "_corn_2021_2023",
      geometry_valid: !!(flags & 8),
      flags,
      lat: (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI,
      lng: x * 360 - 180,
    });
  }
  return points;
}
