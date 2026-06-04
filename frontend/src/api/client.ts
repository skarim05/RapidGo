import axios from "axios";

const client = axios.create({
  baseURL: "",
  timeout: 30000,
});

export interface RouteInfo {
  route_id: string;
  route_short_name: string | null;
  route_long_name: string | null;
  route_color: string | null;
}

export interface DelayByHour {
  hour: number;
  median_delay_seconds: number;
  p90_delay_seconds: number;
  samples: number;
}

export interface HeatmapCell {
  day_of_week: number;
  hour: number;
  p90_delay_seconds: number;
  samples: number;
}

export interface RouteRanking {
  route_id: string;
  route_short_name: string | null;
  median_delay_seconds: number;
  p90_delay_seconds: number;
  samples: number;
}

export interface PredictResult {
  route_id: string;
  hour: number;
  day_of_week: number;
  predicted_delay_seconds: number;
  p90_delay_seconds: number | null;
  confidence: string;
  sample_count: number;
  method: string;
  insufficient_data: boolean;
  ml_predicted_delay_seconds?: number;
}

export const api = {
  getRoutes: () => client.get<RouteInfo[]>("/api/routes"),
  getVehicles: () => client.get("/api/vehicles"),
  getAlerts: () => client.get("/api/alerts"),
  getStatus: () => client.get("/api/status"),
  getRouteShape: (routeId: string) => client.get(`/api/routes/${routeId}/shape`),
  getRouteStops: (routeId: string) => client.get(`/api/routes/${routeId}/stops`),
  getDelaysByHour: (routeId: string, days = 7) =>
    client.get<DelayByHour[]>(`/api/analytics/route/${routeId}/delays-by-hour`, { params: { days } }),
  getHeatmap: (routeId: string, days = 14) =>
    client.get<HeatmapCell[]>(`/api/analytics/route/${routeId}/heatmap`, { params: { days } }),
  getRanking: (days = 7) =>
    client.get<RouteRanking[]>("/api/analytics/routes/ranking", { params: { days } }),
  getCollisions: () => client.get("/api/analytics/collisions"),
  getPredict: (routeId: string, hour?: number, dayOfWeek?: number) =>
    client.get<PredictResult>("/api/predict", {
      params: { route_id: routeId, hour, day_of_week: dayOfWeek },
    }),
};

export default api;
