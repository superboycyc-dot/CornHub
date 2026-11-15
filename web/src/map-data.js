import { number } from "./data.js";
export const FIELD_MIN_ZOOM = 13;
export function fieldSnapshot(feature, data, year, role) {
  const properties = feature.properties;
  const match = (row) =>
    row.field_id === properties.field_id && String(row.year) === String(year);
  const prediction = (data["model/predictions.csv"] || []).find(
    (row) => match(row) && row.prediction_role === role,
  );
  const quality = (data["satellite/features.csv"] || []).find(match);
  const label = (data["core/labels.csv"] || []).find(match);
  const p = number(prediction?.p_silage);
  return {
    field_id: properties.field_id,
    year: String(year),
    role,
    area_ha: number(properties.area_ha),
    p_silage: p,
    predicted_label: p === null ? null : prediction?.predicted_label || null,
    quality_flag: quality?.quality_flag || null,
    label: label?.label || null,
  };
}
export function countiesInView(features, bounds) {
  return features.filter((feature) => {
    const [west, south, east, north] = feature.bbox;
    return (
      east >= bounds.west &&
      west <= bounds.east &&
      north >= bounds.south &&
      south <= bounds.north
    );
  });
}
