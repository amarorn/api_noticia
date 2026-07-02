from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    lake_root: Path = Path("./data/lake")
    lake_primary: str = "local"
    lake_sync_bq_on_write: bool = True
    sources_yaml: Path = Path("./data/sources.yaml")
    collect_lookback_days: int = 7
    rss_max_entries_per_source: int = 160  # 14 fontes ativas → meta ~800 únicos por sync
    news_body_preview_max_chars: int | None = None
    news_sync_fetch_body: bool = True
    gcp_project: str | None = None
    bq_dataset: str = "sports_news_lake"
    gcs_bucket: str | None = None
    gcs_lake_prefix: str = "lake"
    google_application_credentials: Path | None = None
    odds_api_key: str | None = None
    odds_default_sport: str = "soccer_fifa_world_cup"
    odds_default_regions: str = "eu"
    odds_default_markets: str = "h2h"
    odds_default_odds_format: str = "decimal"
    api_football_key: str | None = None
    api_football_base_url: str = "https://v3.football.api-sports.io"
    sofascore_base_url: str = "https://api.sofascore.com/api/v1"
    sofascore_impersonate: str = "chrome124"
    sofascore_timeout_sec: float = 25.0
    superbet_base_url: str = "https://production-superbet-offer-br.freetls.fastly.net"
    superbet_locale: str = "pt-BR"
    superbet_timeout_sec: float = 45.0
    superbet_fetch_retries: int = 2
    superbet_stale_max_age_sec: int = 600
    scorealarm_base_url: str = "https://scorealarm-stats.freetls.fastly.net"
    scorealarm_brand: str = "brsuperbetsport"
    scorealarm_locale: str = "pt-BR"
    scorealarm_timeout_sec: float = 12.0
    scorealarm_fetch_retries: int = 1
    scorealarm_enabled: bool = True
    social_top_picks_enabled: bool = False
    social_top_picks_base_url: str = "https://social-front.freetls.fastly.net"
    social_top_picks_origin: str = "https://superbet.bet.br"
    social_top_picks_timeout_sec: float = 8.0
    superbet_odds_path: Path = Path("data/rounds/superbet_odds.json")
    sofascore_min_interval_sec: float = Field(
        default=0.12,
        validation_alias=AliasChoices(
            "sofascore_min_interval_sec",
            "SOFASCORE_MIN_INTERVAL_SEC",
            "SOFASCORE_MIN_INTERVAL_SECONDS",
        ),
    )
    sofascore_waf_max_retries: int = 3
    sofascore_waf_retry_base_sec: float = 5.0
    sofascore_waf_fail_fast_after: int = 8
    sofascore_waf_cooldown_sec: float = 900.0
    sofascore_fept_dir: Path = Path("data/lake/fept")
    sofascore_stats_dir: Path = Path("data/lake/sofascore")
    sofascore_enrich_dir: Path = Path("data/lake/sofascore/enrich")
    fifa_matches_dir: Path = Path("data/lake/fifa/matches")
    fifa_rankings_cache_path: Path = Path("data/lake/fifa/rankings_live.json")
    fifa_window_cache_path: Path = Path("data/lake/fifa/window_matches.json")
    ner_enabled: bool = False
    ner_model: str = "pierreguillou/ner-bert-base-cased-pt-lenerbr"
    bolao_model_path: Path = Path("models/checkpoints/bolao-unsloth")
    bolao_lm_base_model: str = "unsloth/Qwen2.5-0.5B-Instruct"
    bolao_use_lm: bool = True
    bolao_lm_max_tokens: int = 8
    wc_validation_season: int = 2022
    wc_train_include_fifa_history: bool = True
    wc_train_labels_copa_only: bool = True
    wc_holdout_mode: str = "temporal"  # temporal (80/10/10 cronológico) | edition (Copa holdout)
    wc_train_split_ratio: float = 0.8
    wc_val_split_ratio: float = 0.1
    wc_test_split_ratio: float = 0.1
    wc_squads_path: Path = Path("data/wc/squads_2026.json")
    wc_artifact_dir: Path = Path("data/lake/artifacts/wc_predictor")
    wc_artifact_force_retrain: bool = False
    wc_elo_k: float = 32.0
    wc_elo_home_adv: float = 30.0
    wc_elo_initial: float = 1500.0
    wc_home_adv_goals: float = 0.12
    wc_home_adv_goals_neutral: float = 0.04
    wc_home_adv_corners: float = 0.45
    wc_home_adv_corners_neutral: float = 0.15
    wc_logistic_c: float = 0.85
    wc_logistic_class_weight: str = "balanced"
    wc_logistic_max_iter: int = 3000
    wc_logistic_calibration_cv: int = 5
    wc_calibrator_gate: bool = True
    wc_ensemble_weight_steps: int = 40
    wc_kxl_blend_weight: float = 0.20
    wc_rho_min: float = -0.15
    wc_rho_max: float = 0.05
    wc_rho_step: float = 0.005
    wc_draw_prob_floor: float = 0.18
    wc_favorite_prob_cap: float = 0.78
    wc_favorite_draw_share: float = 0.55
    wc_draw_pick_min_prob: float = 1.0
    wc_draw_balance_gap: float = 0.18
    wc_draw_competitive_margin: float = 0.035
    wc_draw_balanced_favorite_cap: float = 0.50
    wc_mc_simulations: int = 5000
    inplay_fast_mc_simulations: int = 1500
    # ── Basquete In-Play ──
    basket_sport_id: int = 4  # Basquete na Superbet BR (confirmado via /worldcup/superbet/live?all_sports=true)
    basket_match_minutes: int = 40  # feed virtual/simulado da Superbet: 4 quartos de 10min (FIBA-style)
    basket_mc_simulations: int = 5000
    basket_fast_mc_simulations: int = 1500
    basket_prior_weight: float = 96.0  # minutos-equivalente de confiança no prior de mercado (~2 jogos NBA)
    basket_clutch_minute: int = 35  # últimos 5 minutos (jogo de 40min): aumenta variância
    basket_clutch_boost_enabled: bool = True
    basket_clutch_boost: float = 1.15
    basket_lead_admin_factor: float = 0.92  # time vencendo administra ritmo
    basket_trailing_push_factor: float = 1.08  # time perdendo força faltas/3pts
    basket_sigma_ppm: float = 0.35  # desvio padrão de pontos por minuto (calibrável)
    basket_spread_lines: tuple[float, ...] = (-12.5, -9.5, -7.5, -5.5, -4.5, -3.5, -2.5, -1.5, 1.5, 2.5, 3.5, 4.5, 5.5, 7.5, 9.5, 12.5)
    basket_total_lines: tuple[float, ...] = (205.5, 210.5, 215.5, 220.5, 225.5, 230.5)
    # Fase 1 in-play (docs/specs/spec-fase-1-quickwins-inplay.md)
    inplay_use_nhpp: bool = True
    inplay_use_market_shrinkage: bool = True
    inplay_momentum_on_remaining: bool = True
    inplay_score_lambda_adjust: bool = False
    inplay_score_lambda_adjust_with_sofascore: bool = True
    inplay_score_lambda_adjust_with_scorealarm: bool = True
    inplay_live_stats_lambda_adjust: bool = True
    inplay_live_stats_max_shift: float = 0.12
    inplay_xg_lambda_adjust: bool = True
    inplay_xg_max_shift: float = 0.25
    inplay_xg_weight_max: float = 0.40
    inplay_xg_aggressive_enabled: bool = True
    inplay_xg_aggressive_cap: float = 0.40
    inplay_xg_aggressive_weight_max: float = 0.65
    inplay_h2h_adjust: bool = True
    inplay_trailing_chase_boost: bool = True
    inplay_use_calibrated_coefficients: bool = True
    inplay_use_calibrated_nhpp: bool = True
    inplay_nhpp_min_observations: int = 500
    wc_xg_lambda_blend_enabled: bool = True
    wc_xg_lambda_blend_weight: float = 0.35
    inplay_tune_min_snapshots: int = 50
    inplay_use_ensemble: bool = True
    inplay_ensemble_hawkes: bool = True
    inplay_ensemble_gbm: bool = True
    inplay_ensemble_shadow_mode: bool = True
    inplay_ensemble_ab_log_ticks: bool = True
    inplay_ensemble_min_feedback_hi: int = 150
    inplay_ensemble_prod_feedback_hi: int = 500
    inplay_ensemble_min_tick_examples: int = 150
    inplay_ensemble_min_inplay_delta: float = 0.015
    # Fase 4 — carteira / feedback loop (docs/specs/spec-fase-4-feedback-loop.md)
    wallet_dashboard_enabled: bool = True
    wallet_reconcile_window_sec: int = 300
    wallet_inbox_enabled: bool = True
    wallet_inbox_dir: str = "inbox/wallet"
    wallet_inbox_auto_reconcile: bool = True
    wallet_inbox_stale_days: int = 7
    inplay_synthetic_tick_weight: float = 2.0
    inplay_synthetic_min_examples: int = 50
    lgn_min_samples: int = 30
    lgn_bootstrap_samples: int = 2000
    ev_min_edge: float = 0.03
    ev_recommendation_min_threshold: float = 0.05
    live_ev_min_edge: float = 0.055
    coase_bookmaker_margin: float = 0.05
    coase_transaction_cost: float = 0.0
    # Finalização automática Superbet (salvar gold + retreino in-play)
    superbet_finalize_enabled: bool = True
    superbet_finalize_retrain: bool = True
    superbet_finalize_user_id: str = "jamarorn"
    superbet_finalize_retrain_gbm: bool = True
    superbet_finalize_retrain_feedback: bool = True
    superbet_finalize_retrain_coefficients: bool = False
    superbet_finalize_min_confidence: float = 0.7
    superbet_finalize_settle_open_bets: bool = True
    # Poll contínuo Superbet (seleções / Copa)
    superbet_poll_wc_enabled: bool = True
    superbet_poll_interval_sec: int = 120
    superbet_poll_wc_phase: str = "group"
    superbet_poll_watchlist_enabled: bool = True
    superbet_poll_watchlist_max: int = 24
    # Widget Sportradar LMT Plus (mesmo feed Betradar da Superbet — requer licença)
    sportradar_client_id: str | None = None
    sportradar_language: str = "pt_br"
    inplay_use_sofascore_live: bool = True
    inplay_sofascore_waf_max_retries: int = 0
    inplay_halftime_adjust: bool = True
    combo_last10_fetch_incidents: bool = False
    # ── Guardas de qualidade de aposta ──
    live_min_market_odd: float = 1.25  # nunca recomendar abaixo desta odd
    live_min_edge_pp: float = 7.0  # mínimo 7pp de edge (model_prob - implied_prob)
    live_midgame_strict_minute: int = 45  # após 45' hit rate cai no histórico reconciliado
    live_midgame_ev_multiplier: float = 1.75
    live_midgame_min_edge_pp: float = 10.0
    live_max_minute_full_advice: int = 85  # após este minuto, exigir EV muito alto
    live_late_game_ev_multiplier: float = 3.0  # multiplicador do threshold no fim de jogo
    live_late_game_min_edge_pp: float = 12.0
    live_block_minute: int = 45  # P0: sem novos aportes FT após 45' (hit rate histórico)
    live_block_2h_minute: int = 82  # mercados 2T até ~82' (tempo restante mínimo)
    live_hard_stop_minute: int = 88  # bloqueia TODAS as apostas novas (hit 0% em 90+')
    live_cashout_use_trend: bool = True  # funde wc_trend_advisor em advise_cashout
    live_ht_over_trap_minute: int = 35  # aviso over 1T com poucos minutos restantes
    live_ht_over_trap_block_dead: bool = True  # bloqueia registro de over 1T já morto
    live_2h_viable_min_prob: float = 0.06  # painel 2T: prob. mínima para listar
    live_2h_viable_max_markets: int = 12
    bet_guardrails_enabled: bool = True
    bet_one_per_market_enabled: bool = True
    bet_max_stake: float = 50.0  # teto por bilhete (R$) — evita overexposure manual
    bet_default_stake_brl: float = 10.0
    bet_use_fractional_kelly: bool = False
    bet_max_stake_pct: float = 5.0
    bet_stop_loss_brl: float = 200.0
    bet_require_minute_extension: bool = True  # extensão precisa minuto resolvível
    bet_block_multis_late: bool = True  # múltiplas/combos bloqueados após live_block_minute
    super_multipla_bonus_pct: float = 0.05  # +5% no retorno (promo Superbet)
    super_multipla_min_leg_odd: float = 1.35  # odd mínima por perna para elegir bônus
    dixit_sigma: float = 2.0
    mlflow_tracking_uri: str = "sqlite:///./mlflow.db"
    mlflow_experiment_wc: str = "api-noticia/wc-benchmark"
    mlflow_experiment_wc_train: str = "api-noticia/wc-train"
    mlflow_experiment_bolao: str = "api-noticia/bolao-benchmark"
    # Seleção de modelo WC em runtime (sem retreino): auto usa melhor implementável do benchmark/MLflow
    wc_model_selection_mode: str = "auto"  # ensemble | auto
    wc_model_selection_metric: str = "brier"  # brier | accuracy
    wc_model_selection_source: str = "benchmark"  # benchmark | mlflow | registry
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str | None = None
    # ── Deep Research (Pré-Jogo) ──
    perplexity_api_key: str | None = None
    perplexity_model: str = "sonar-pro"
    moonshot_api_key: str | None = None
    moonshot_model: str = "moonshot-v1-128k"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    pregame_research_cache_ttl_sec: int = 3600  # 1h de cache por partida
    # ── Copiloto ao vivo (OpenAI GPT) ──
    live_copilot_enabled: bool = True
    live_copilot_poll_enabled: bool = True
    live_copilot_cache_ttl_sec: int = 25
    live_copilot_temperature: float = 0.2
    live_copilot_max_tokens: int = 1200
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

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
