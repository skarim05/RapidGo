import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import api, { HeatmapCell } from "../api/client";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface DelayHeatmapProps {
  routeId: string | null;
}

function colorForDelay(sec: number, max: number): string {
  if (max <= 0) return "#1a2332";
  const t = Math.min(sec / max, 1);
  const r = Math.round(30 + t * 200);
  const g = Math.round(80 - t * 60);
  const b = Math.round(120 - t * 80);
  return `rgb(${r},${g},${b})`;
}

export default function DelayHeatmap({ routeId }: DelayHeatmapProps) {
  const { data } = useQuery({
    queryKey: ["heatmap", routeId],
    queryFn: async () => (routeId ? (await api.getHeatmap(routeId, 14)).data : []),
    enabled: !!routeId,
  });

  const { grid, maxP90 } = useMemo(() => {
    const cells = (data ?? []) as HeatmapCell[];
    const max = Math.max(...cells.map((c) => c.p90_delay_seconds), 1);
    const lookup = new Map<string, HeatmapCell>();
    cells.forEach((c) => lookup.set(`${c.day_of_week}-${c.hour}`, c));
    const grid: (HeatmapCell | null)[][] = [];
    for (let dow = 0; dow < 7; dow++) {
      const row: (HeatmapCell | null)[] = [];
      for (let h = 0; h < 24; h++) {
        row.push(lookup.get(`${dow}-${h}`) ?? null);
      }
      grid.push(row);
    }
    return { grid, maxP90: max };
  }, [data]);

  if (!routeId) return null;

  return (
    <div>
      <h3 style={{ margin: "0 0 0.5rem" }}>Delay heatmap (P90, 14 days)</h3>
      {!data?.length ? (
        <p style={{ color: "#8b9cb3", fontSize: 14 }}>Collecting data… heatmap fills in as delays are recorded.</p>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "32px 1fr", gap: 4, fontSize: 11 }}>
            <div />
            <div className="heatmap-grid" style={{ gridTemplateColumns: "repeat(24, 1fr)" }}>
              {Array.from({ length: 24 }, (_, h) => (
                <span key={h} style={{ textAlign: "center", color: "#8b9cb3" }}>
                  {h % 6 === 0 ? h : ""}
                </span>
              ))}
            </div>
            {grid.map((row, dow) => (
              <div key={dow} style={{ display: "contents" }}>
                <span style={{ color: "#8b9cb3" }}>{DAYS[dow]}</span>
                <div className="heatmap-grid">
                  {row.map((cell, h) => (
                    <div
                      key={h}
                      className="heatmap-cell"
                      title={
                        cell
                          ? `P90 ${Math.round(cell.p90_delay_seconds / 60)}m (${cell.samples} samples)`
                          : "No data"
                      }
                      style={{
                        background: cell
                          ? colorForDelay(cell.p90_delay_seconds, maxP90)
                          : "#1a2332",
                      }}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 11, color: "#8b9cb3", marginTop: 8 }}>
            Darker red = higher P90 delay. Based on your locally collected GTFS-RT history.
          </p>
        </>
      )}
    </div>
  );
}
