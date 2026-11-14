import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./style.css";
import { loadData, number, present } from "./data";
const show = (v, missing = "缺测") => (present(v) ? String(v) : missing);
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
      <div ref={el} className="map" aria-label="田块地图" />
      {!fields?.features.length && (
        <div className="map-empty">
          真实田块边界尚未提供
          <br />
          <small>等待 A：core/fields.geojson · EPSG:4326</small>
        </div>
      )}
      <span className="map-note">经度、纬度 · 不使用外部底图</span>
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
    return <p className="empty">缺测：没有真实 NDVI 观测，不生成曲线。</p>;
  const dates = good.map((r) => Date.parse(r.date)),
    min = Math.min(...dates),
    max = Math.max(...dates);
  return (
    <>
      <svg
        viewBox="0 0 640 190"
        role="img"
        aria-label="真实 NDVI 观测点；不插值、不连线"
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
              {r.date} NDVI={r.ndvi} 有效比例={r.valid_pixel_fraction} scene_id=
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
        仅展示观测点，不插值。棕色：有效比例不足 0.5 或缺测。来源
        satellite/timeseries.csv
      </small>
      <details>
        <summary>逐景来源</summary>
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
    <p className="empty">尚未提供记录</p>
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
        <span>BARC / 田块证据工作台</span>
        <span className="stage">阶段 01 · 本地集成</span>
      </header>
      <main>
        <div className="intro">
          <div>
            <p className="eyebrow">FIELD EVIDENCE · 2021—2023</p>
            <h1>从真实田块，查看收获证据。</h1>
            <p>
              卫星观测、模型青贮概率与数据质量分别呈现。结果仅代表选定范围。
            </p>
          </div>
          <button onClick={reload}>重新加载数据</button>
        </div>
        <div className="toolbar">
          <label>
            年份{" "}
            <select value={year} onChange={(e) => setYear(e.target.value)}>
              {["2021", "2022", "2023"].map((y) => (
                <option key={y}>{y}</option>
              ))}
            </select>
          </label>
          <label>
            预测用途{" "}
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="oof">oof · 田块外验证</option>
              <option value="inference">inference · 全量推断</option>
            </select>
          </label>
          <label>
            田块{" "}
            <select value={fieldId} onChange={(e) => setId(e.target.value)}>
              <option value="">选择真实田块</option>
              {allIds.map((i) => (
                <option key={i}>{i}</option>
              ))}
            </select>
          </label>
          <span>{loading ? "正在加载…" : "来源：data/processed 发布副本"}</span>
        </div>
        <div className="grid">
          <section className="card map-card">
            <h2>
              田块地图 <small>真实边界</small>
            </h2>
            <Map fields={fields} selected={fieldId} onSelect={setId} />
          </section>
          <section className="card">
            <h2>田块详情</h2>
            <h3>{fieldId || "等待共同样本"}</h3>
            <dl>
              {Object.entries({
                年份: year,
                "面积（ha）": show(boundary?.area_ha),
                "官方 ID": show(boundary?.source_field_id),
                标签: show(label?.label),
                来源数据集: show(boundary?.source_dataset_id),
                模型青贮概率: show(prediction?.p_silage, "未计算"),
                预测类别: show(prediction?.predicted_label, "未计算"),
                模型版本: show(prediction?.model_version, "未计算"),
                预测用途: role,
              }).map(([k, v]) => (
                <React.Fragment key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </React.Fragment>
              ))}
            </dl>
            <p className="notice">
              模型概率不是准确率；未提供预测时显示未计算。来源
              model/predictions.csv。
            </p>
          </section>
          <section className="card">
            <h2>
              NDVI 时序 <small>{year} · 不插值</small>
            </h2>
            <Curve rows={selected(d["satellite/timeseries.csv"])} />
          </section>
          <section className="card">
            <h2>卫星数据质量</h2>
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
              来源 satellite/features.csv · 暂定质量规则，不代表预测可靠性。
            </small>
          </section>
          <section className="card">
            <h2>
              面积与经济汇总 <small>D 的原始结果</small>
            </h2>
            {summaryMatches ? (
              <>
                <p>
                  {summary.status === "pending" ? "未计算" : summary.status}
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
                          "未计算",
                        )}
                      </dd>
                    </React.Fragment>
                  ))}
                </dl>
                <p>
                  经济情景：
                  {summary.economic_scenario
                    ? JSON.stringify(summary.economic_scenario)
                    : "未计算"}
                </p>
                <p>{JSON.stringify(summary.notes)}</p>
              </>
            ) : (
              <p className="empty">
                未计算：尚无当前年份与用途的 summary.json。前端不自行统计。
              </p>
            )}
          </section>
          <section className="card">
            <h2>模型验证</h2>
            {metrics?.status === "evaluated" &&
            metrics.prediction_role === role ? (
              <pre>{JSON.stringify(metrics, null, 2)}</pre>
            ) : (
              <p className="empty">未计算：尚无匹配用途的真实验证指标。</p>
            )}
          </section>
          <section className="card wide">
            <h2>核查清单</h2>
            <p>
              来源 analysis/review_queue.csv ·
              启发式优先级，不是误判概率或经济价值。
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
            <h2>待补数据与接入检查</h2>
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
                      !present(p?.p_silage) && "无预测",
                      (!f || f.quality_flag !== "usable") &&
                        `卫星质量：${f?.quality_flag || "缺测"}`,
                    ]
                      .filter(Boolean)
                      .join("；"),
                  };
                })
                .filter((r) => r.reason)}
              cols={["field_id", "year", "prediction_role", "reason"]}
            />
            <details open>
              <summary>文件状态与加载失败提示</summary>
              {Object.entries(errors).map(([name, e]) => (
                <p className="file-status" key={name}>
                  <code>{name}</code>
                  <span>{e}</span>
                </p>
              ))}
              {!Object.keys(errors).length && <p>全部合同文件已读取。</p>}
            </details>
            {!!orphan.length && (
              <details>
                <summary>未匹配边界的记录（不丢弃）</summary>
                <pre>{orphan.join("\n")}</pre>
              </details>
            )}
            <details>
              <summary>输入记录数</summary>
              <pre>
                {Object.entries(d)
                  .map(
                    ([k, v]) =>
                      `${k}: ${Array.isArray(v) ? v.length : (v.features?.length ?? "JSON 对象")}`,
                  )
                  .join("\n")}
              </pre>
            </details>
          </section>
        </div>
        <footer>
          合同：docs/team-contract.md · 边界由 A 提供 · 时序 B · 模型 C · 汇总 D
          · 页面 E
        </footer>
      </main>
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
