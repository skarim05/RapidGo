import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import { useQueries, useQuery } from "@tanstack/react-query";
import api, { DelayByHour } from "../api/client";

interface RouteChartProps {
  routeId: string | null;
  compareRouteIds: string[];
}

function formatDelay(sec: number) {
  const m = Math.round(sec / 60);
  return m >= 1 ? `${m} min` : `${sec}s`;
}

export default function RouteChart({ routeId, compareRouteIds }: RouteChartProps) {
  const ids = routeId ? [routeId, ...compareRouteIds.filter((id) => id !== routeId)] : [];

  const routeQueries = useQueries({
    queries: ids.map((id) => ({
      queryKey: ["delays-by-hour", id],
      queryFn: async () => (await api.getDelaysByHour(id, 7)).data as DelayByHour[],
      enabled: !!id,
    })),
  });

  const { data: ranking } = useQuery({
    queryKey: ["ranking"],
    queryFn: async () => (await api.getRanking(7)).data,
    refetchInterval: 60000,
  });

  if (!routeId) {
    return (
      <div>
        <h3 style={{ margin: "0 0 0.5rem" }}>Worst routes (7 days)</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={ranking?.slice(0, 10) ?? []} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" />
            <XAxis dataKey="route_short_name" tick={{ fill: "#8b9cb3", fontSize: 11 }} />
            <YAxis tickFormatter={(v) => `${Math.round(v / 60)}m`} tick={{ fill: "#8b9cb3" }} />
            <Tooltip
              formatter={(v: number) => formatDelay(v)}
              contentStyle={{ background: "#1a2332", border: "1px solid #2d3a4f" }}
            />
            <Bar dataKey="p90_delay_seconds" name="P90 delay" fill="#e85d5d" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  const primary: DelayByHour[] = routeQueries[0]?.data ?? [];
  const chartData = Array.from({ length: 24 }, (_, hour) => {
    const row: Record<string, number | string> = { hour: `${hour}:00` };
    routeQueries.forEach((q, i) => {
      const point = q.data?.find((d) => d.hour === hour);
      row[`route_${ids[i]}`] = point?.median_delay_seconds ?? 0;
    });
    return row;
  });

  const colors = ["#3b9eff", "#f0a020", "#4ade80"];

  return (
    <div>
      <h3 style={{ margin: "0 0 0.5rem" }}>Median delay by hour of day</h3>
      {primary.length === 0 ? (
        <p style={{ color: "#8b9cb3", fontSize: 14 }}>
          No delay data yet. The backend polls GTFS-RT every ~45s — check back after it runs for a while.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" />
            <XAxis dataKey="hour" tick={{ fill: "#8b9cb3", fontSize: 10 }} interval={3} />
            <YAxis tickFormatter={(v) => `${Math.round(Number(v) / 60)}m`} tick={{ fill: "#8b9cb3" }} />
            <Tooltip
              formatter={(v: number) => formatDelay(v)}
              contentStyle={{ background: "#1a2332", border: "1px solid #2d3a4f" }}
            />
            <Legend />
            {ids.map((id, i) => (
              <Line
                key={id}
                type="monotone"
                dataKey={`route_${id}`}
                name={id}
                stroke={colors[i % colors.length]}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
