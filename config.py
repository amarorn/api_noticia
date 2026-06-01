from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    lake_root: Path = Path("./data/lake")
    sources_yaml: Path = Path("./data/sources.yaml")
    collect_lookback_days: int = 7
    gcp_project: str | None = None
    bq_dataset: str = "sports_news_lake"
    gcs_bucket: str | None = None
    odds_api_key: str | None = None
    odds_default_sport: str = "soccer_fifa_world_cup"
    odds_default_regions: str = "eu"
    odds_default_markets: str = "h2h"
    odds_default_odds_format: str = "decimal"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @property
    def bronze_path(self) -> Path:
        return self.lake_root / "bronze"

    @property
    def silver_path(self) -> Path:
        return self.lake_root / "silver"

    @property
    def gold_path(self) -> Path:
        return self.lake_root / "gold"

    @property
    def fixtures_path(self) -> Path:
        return self.lake_root / "fixtures"


settings = Settings()
