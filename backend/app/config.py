from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://rapidgo:rapidgo@localhost:5432/rapidgo"
    gtfs_static_url: str = "https://gtfs.edmonton.ca/TMGTFSRealTimeWebService/GTFS/gtfs.zip"
    gtfs_rt_vehicle_url: str = (
        "http://gtfs.edmonton.ca/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb"
    )
    gtfs_rt_trip_url: str = (
        "http://gtfs.edmonton.ca/TMGTFSRealTimeWebService/TripUpdate/TripUpdates.pb"
    )
    gtfs_rt_alert_url: str = (
        "http://gtfs.edmonton.ca/TMGTFSRealTimeWebService/Alert/Alerts.pb"
    )
    poll_interval_seconds: int = 45
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    socrata_collision_dataset: str = "mf6n-s5ts"
    socrata_base_url: str = "https://data.edmonton.ca/resource"
    timezone: str = "America/Edmonton"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
