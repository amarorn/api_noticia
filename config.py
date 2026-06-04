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
    rss_max_entries_per_source: int = 160  # 14 fontes ativas → meta ~800 únicos por sync
    news_body_preview_max_chars: int | None = None
    news_sync_fetch_body: bool = True
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
    wc_squads_path: Path = Path("data/wc/squads_2026.json")
    wc_artifact_dir: Path = Path("data/lake/artifacts/wc_predictor")
    wc_artifact_force_retrain: bool = False
    wc_elo_k: float = 32.0
    wc_elo_home_adv: float = 30.0
    wc_elo_initial: float = 1500.0
    wc_home_adv_goals: float = 0.12
    wc_home_adv_goals_neutral: float = 0.04
    wc_logistic_c: float = 0.85
    wc_logistic_class_weight: str = "balanced"
    wc_logistic_max_iter: int = 3000
    wc_ensemble_weight_steps: int = 40
    wc_kxl_blend_weight: float = 0.20
    wc_rho_min: float = -0.20
    wc_rho_max: float = 0.20
    wc_rho_step: float = 0.01
    wc_draw_prob_floor: float = 0.18
    lgn_min_samples: int = 30
    lgn_bootstrap_samples: int = 2000
    ev_min_edge: float = 0.03
    coase_bookmaker_margin: float = 0.05
    coase_transaction_cost: float = 0.0
    dixit_sigma: float = 2.0
    mlflow_tracking_uri: str = "sqlite:///./mlflow.db"
    mlflow_experiment_wc: str = "api-noticia/wc-benchmark"
    mlflow_experiment_bolao: str = "api-noticia/bolao-benchmark"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str | None = None

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
