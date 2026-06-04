import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import MapView from "../components/MapView";
import RouteChart from "../components/RouteChart";
import DelayHeatmap from "../components/DelayHeatmap";

export default function Dashboard() {
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [compareRouteId, setCompareRouteId] = useState<string>("");
  const [showCollisions, setShowCollisions] = useState(true);
  const [predictHour, setPredictHour] = useState<number>(new Date().getHours());

  const { data: routes } = useQuery({
    queryKey: ["routes"],
    queryFn: async () => (await api.getRoutes()).data,
  });

  const { data: status } = useQuery({
    queryKey: ["status"],
    queryFn: async () => (await api.getStatus()).data,
    refetchInterval: 30000,
  });

  const { data: alerts } = useQuery({
    queryKey: ["alerts"],
    queryFn: async () => (await api.getAlerts()).data,
    refetchInterval: 60000,
  });

  const { data: predict } = useQuery({
    queryKey: ["predict", selectedRouteId, predictHour],
    queryFn: async () =>
      selectedRouteId
        ? (await api.getPredict(selectedRouteId, predictHour)).data
        : null,
    enabled: !!selectedRouteId,
  });

  const sortedRoutes = useMemo(
    () =>
      [...(routes ?? [])].sort((a, b) =>
        (a.route_short_name ?? "").localeCompare(b.route_short_name ?? "", undefined, {
          numeric: true,
        })
      ),
    [routes]
  );

  const compareRouteIds = compareRouteId ? [compareRouteId] : [];

  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>RapidGo — Edmonton ETS Analytics</h1>
        <span className={`status-badge ${status?.rt_feed_stale ? "stale" : ""}`}>
          RT feed: {status?.rt_feed_stale ? "stale" : "live"}
          {status?.gtfs_rt_last_poll && ` · last poll ${new Date(status.gtfs_rt_last_poll).toLocaleTimeString()}`}
        </span>
      </header>

      <aside className="sidebar">
        {alerts?.length > 0 && (
          <div className="alert-banner">
            <strong>Service alert</strong>
            <div>{alerts[0].header_text || alerts[0].description_text}</div>
          </div>
        )}

        <label htmlFor="route-select">Route</label>
        <select
          id="route-select"
          value={selectedRouteId ?? ""}
          onChange={(e) => setSelectedRouteId(e.target.value || null)}
        >
          <option value="">Select a route…</option>
          {sortedRoutes.map((r) => (
            <option key={r.route_id} value={r.route_id}>
              {r.route_short_name ?? r.route_id} — {r.route_long_name ?? ""}
            </option>
          ))}
        </select>

        <label htmlFor="compare-select">Compare with (optional)</label>
        <select
          id="compare-select"
          value={compareRouteId}
          onChange={(e) => setCompareRouteId(e.target.value)}
        >
          <option value="">None</option>
          {sortedRoutes
            .filter((r) => r.route_id !== selectedRouteId)
            .map((r) => (
              <option key={r.route_id} value={r.route_id}>
                {r.route_short_name ?? r.route_id}
              </option>
            ))}
        </select>

        <div className="checkbox-row">
          <input
            type="checkbox"
            id="collisions"
            checked={showCollisions}
            onChange={(e) => setShowCollisions(e.target.checked)}
          />
          <label htmlFor="collisions" style={{ margin: 0 }}>
            Collision heatmap (annual open data)
          </label>
        </div>

        {selectedRouteId && (
          <>
            <div className="section-title">Delay prediction</div>
            <label htmlFor="predict-hour">Hour of day</label>
            <input
              id="predict-hour"
              type="number"
              min={0}
              max={23}
              value={predictHour}
              onChange={(e) => setPredictHour(Number(e.target.value))}
            />
            {predict && (
              <div className="predict-box">
                <div className="delay-value">
                  ~{Math.round(predict.predicted_delay_seconds / 60)} min
                </div>
                <div style={{ fontSize: 12, color: "#8b9cb3" }}>
                  Confidence: {predict.confidence} · {predict.sample_count} samples · {predict.method}
                  {predict.insufficient_data && " · model still learning"}
                </div>
                {predict.ml_predicted_delay_seconds != null && (
                  <div style={{ fontSize: 12, marginTop: 4 }}>
                    ML estimate: ~{Math.round(predict.ml_predicted_delay_seconds / 60)} min
                  </div>
                )}
              </div>
            )}
          </>
        )}

        <p style={{ fontSize: 11, color: "#8b9cb3", marginTop: "1rem" }}>
          GTFS static: {status?.gtfs_static_loaded_at ? "loaded" : "not loaded — run admin refresh"}
        </p>
      </aside>

      <div className="main-content">
        <MapView
          selectedRouteId={selectedRouteId}
          showCollisions={showCollisions}
          compareRouteIds={compareRouteIds}
        />
        <div className="charts-panel">
          <div className="chart-row">
            <RouteChart routeId={selectedRouteId} compareRouteIds={compareRouteIds} />
            <DelayHeatmap routeId={selectedRouteId} />
          </div>
        </div>
      </div>
    </div>
  );
}
