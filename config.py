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
    api_football_key: str | None = None
    api_football_base_url: str = "https://v3.football.api-sports.io"
    ner_enabled: bool = False
    ner_model: str = "pierreguillou/ner-bert-base-cased-pt-lenerbr"
    bolao_model_path: Path = Path("models/checkpoints/bolao-unsloth")
    bolao_lm_base_model: str = "unsloth/Qwen2.5-0.5B-Instruct"
    bolao_use_lm: bool = True
    bolao_lm_max_tokens: int = 8
    wc_validation_season: int = 2022
    lgn_min_samples: int = 30
    lgn_bootstrap_samples: int = 2000
    ev_min_edge: float = 0.03
    coase_bookmaker_margin: float = 0.05
    coase_transaction_cost: float = 0.0
    dixit_sigma: float = 2.0
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

    @property
    def wc_validation_fixtures_path(self) -> Path:
        return self.fixtures_path / f"world_cup_{self.wc_validation_season}.parquet"


settings = Settings()
