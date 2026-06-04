import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, GeoJSON, CircleMarker, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat/dist/leaflet-heat.js";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

const EDMONTON_CENTER: [number, number] = [53.5461, -113.4938];

interface MapViewProps {
  selectedRouteId: string | null;
  showCollisions: boolean;
  compareRouteIds: string[];
}

function FitBounds({ geojson }: { geojson: GeoJSON.GeoJsonObject | null }) {
  const map = useMap();
  useEffect(() => {
    if (!geojson) return;
    const layer = L.geoJSON(geojson);
    const bounds = layer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40] });
  }, [geojson, map]);
  return null;
}

function HeatLayer({ enabled }: { enabled: boolean }) {
  const map = useMap();
  const { data } = useQuery({
    queryKey: ["collisions"],
    queryFn: async () => (await api.getCollisions()).data,
    enabled,
  });

  useEffect(() => {
    if (!enabled || !data?.features?.length) return;
    const points: [number, number, number][] = data.features.map(
      (f: { geometry: { coordinates: number[] }; properties: { intensity?: number; collision_count?: number } }) => [
        f.geometry.coordinates[1],
        f.geometry.coordinates[0],
        (f.properties.intensity || f.properties.collision_count || 1) as number,
      ]
    );
    const heat = L.heatLayer(points, { radius: 18, blur: 22, maxZoom: 15 });
    heat.addTo(map);
    return () => {
      map.removeLayer(heat);
    };
  }, [map, data, enabled]);

  return null;
}

export default function MapView({ selectedRouteId, showCollisions, compareRouteIds }: MapViewProps) {
  const { data: vehicles, isLoading: vehiclesLoading } = useQuery({
    queryKey: ["vehicles"],
    queryFn: async () => (await api.getVehicles()).data,
    refetchInterval: 20000,
  });

  const routeIds = useMemo(() => {
    const ids = new Set<string>();
    if (selectedRouteId) ids.add(selectedRouteId);
    compareRouteIds.forEach((id) => ids.add(id));
    return [...ids];
  }, [selectedRouteId, compareRouteIds]);

  const { data: shapeData } = useQuery({
    queryKey: ["shape", selectedRouteId],
    queryFn: async () =>
      selectedRouteId ? (await api.getRouteShape(selectedRouteId)).data : null,
    enabled: !!selectedRouteId,
  });

  const { data: stopsData } = useQuery({
    queryKey: ["stops", selectedRouteId],
    queryFn: async () =>
      selectedRouteId ? (await api.getRouteStops(selectedRouteId)).data : null,
    enabled: !!selectedRouteId,
  });

  const vehicleMarkers = vehicles?.features ?? [];

  return (
    <div className="map-wrap">
      <MapContainer center={EDMONTON_CENTER} zoom={12} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {shapeData && (
          <>
            <GeoJSON
              key={selectedRouteId}
              data={shapeData}
              pathOptions={{ color: "#3b9eff", weight: 4, opacity: 0.9 }}
            />
            <FitBounds geojson={shapeData} />
          </>
        )}
        {stopsData && (
          <GeoJSON
            data={stopsData}
            pointToLayer={(_f, latlng) =>
              L.circleMarker(latlng, { radius: 4, color: "#fff", fillColor: "#3b9eff", fillOpacity: 0.8 })
            }
          />
        )}
        {vehicleMarkers.map(
          (f: {
            geometry: { coordinates: number[] };
            properties: { route_id?: string; vehicle_id?: string };
          }) => (
            <CircleMarker
              key={f.properties.vehicle_id}
              center={[f.geometry.coordinates[1], f.geometry.coordinates[0]]}
              radius={6}
              pathOptions={{
                color: "#1a2332",
                fillColor: "#4ade80",
                fillOpacity: 0.9,
                weight: 1,
              }}
            />
          )
        )}
        {showCollisions && <HeatLayer enabled />}
      </MapContainer>
      <div
        style={{
          position: "absolute",
          bottom: 8,
          left: 8,
          background: "rgba(26,35,50,0.9)",
          padding: "4px 8px",
          borderRadius: 4,
          fontSize: 12,
        }}
      >
        {vehiclesLoading ? "Loading buses…" : `${vehicleMarkers.length} buses (last 5 min)`}
        {routeIds.length > 1 && ` · comparing ${routeIds.length} routes`}
      </div>
    </div>
  );
}
