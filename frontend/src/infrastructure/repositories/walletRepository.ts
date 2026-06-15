/**
 * Repositório da carteira do usuário (Fase 4).
 *
 * Endpoints:
 *  POST /user/transactions/upload       — sobe CSV
 *  GET  /user/transactions/summary      — KPIs
 *  POST /user/transactions/reconcile    — gera silver
 *  GET  /user/transactions/reconciliation — tabela paginada
 *  GET  /user/transactions/model-errors — heatmap
 *  GET  /user/wallet/sync-status        — inbox / CSV desatualizado
 *  POST /user/wallet/import-inbox        — importa CSVs da pasta inbox
 */
import { apiFetch } from "../api/client";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";
const API_KEY = import.meta.env.VITE_API_KEY?.trim() || undefined;

export interface DailyPnl {
  date: string;
  staked: number;
  won: number;
  pnl: number;
  n_bets: number;
  is_today?: boolean;
  supplemental?: boolean;
}

export interface GameTypeBreakdown {
  category: string;
  staked: number;
  won: number;
  pnl: number;
  n_bets: number;
}

export interface BalancePoint {
  at: string;
  balance: number;
  type: string;
}

export interface WalletSummary {
  user_id: string;
  n_transactions: number;
  n_bets_placed: number;
  n_bets_won: number;
  hit_rate: number;
  total_staked: number;
  total_won: number;
  pnl: number;
  roi: number;
  total_deposits: number;
  current_balance: number;
  period_start: string | null;
  period_end: string | null;
  today?: string | null;
  daily_pnl: DailyPnl[];
  by_game_type: GameTypeBreakdown[];
  balance_series: BalancePoint[];
}

export interface ReconciliationItem {
  placed_at: string | null;
  stake: number;
  won_amount: number;
  pnl: number;
  won: boolean;
  event_id: number | null;
  home_team: string | null;
  away_team: string | null;
  match_minute: number | null;
  home_score: number | null;
  away_score: number | null;
  match_confidence: number;
  model_generosity_home: number | null;
  model_generosity_away: number | null;
}

export interface ReconciliationTable {
  total: number;
  items: ReconciliationItem[];
}

export interface HeatmapBucket {
  min_bucket?: string;
  diff_bucket?: string;
  bucket?: string;
  n_bets: number;
  avg_brier: number;
  hit_rate: number;
  total_pnl: number;
}

export interface ModelErrors {
  buckets: HeatmapBucket[];
  min_buckets: HeatmapBucket[];
  diff_buckets: HeatmapBucket[];
  n_total_bets?: number;
}

export interface UploadResponse {
  upload_id: string;
  user_id: string;
  n_rows: number;
  n_inplay_bets_placed: number;
  n_wins: number;
  total_staked: number;
  total_won: number;
  pnl: number;
  file_path: string;
}

export interface WalletSyncStatus {
  user_id: string;
  inbox_dir: string;
  pending_csv_files: string[];
  n_pending: number;
  last_upload_at: string | null;
  days_since_upload: number | null;
  n_uploads: number;
  stale: boolean;
  stale_threshold_days: number;
  inbox_enabled: boolean;
}

export interface WalletInboxImportResult {
  user_id: string;
  scanned_at: string;
  n_imported: number;
  n_skipped: number;
  imports: Array<{
    file_path: string;
    upload_id: string | null;
    n_rows: number;
    imported: boolean;
    skipped: boolean;
    reason: string | null;
  }>;
  reconciliation: {
    n_pairs?: number;
    n_high_confidence?: number;
    error?: string;
  } | null;
}

export const walletRepository = {
  async upload(file: File, userId: string): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file);

    const url = `${API_BASE}/user/transactions/upload?user_id=${encodeURIComponent(userId)}`;
    const response = await fetch(url, {
      method: "POST",
      body: form,
      headers: {
        ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
      },
    });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = body.detail ?? body.message ?? detail;
      } catch {
        /* noop */
      }
      throw new Error(String(detail));
    }
    return response.json();
  },

  getSummary(userId: string): Promise<WalletSummary> {
    return apiFetch<WalletSummary>(
      `/user/transactions/summary?user_id=${encodeURIComponent(userId)}`,
    );
  },

  reconcile(userId: string): Promise<{
    status: string;
    n_pairs: number;
    n_matched_high_confidence?: number;
    match_rate?: number;
  }> {
    return apiFetch(`/user/transactions/reconcile?user_id=${encodeURIComponent(userId)}`, {
      method: "POST",
    });
  },

  getReconciliation(userId: string, limit = 50, offset = 0): Promise<ReconciliationTable> {
    const qs = new URLSearchParams({
      user_id: userId,
      limit: String(limit),
      offset: String(offset),
    });
    return apiFetch<ReconciliationTable>(`/user/transactions/reconciliation?${qs}`);
  },

  getModelErrors(userId: string): Promise<ModelErrors> {
    return apiFetch<ModelErrors>(
      `/user/transactions/model-errors?user_id=${encodeURIComponent(userId)}`,
    );
  },

  getSyncStatus(userId: string): Promise<WalletSyncStatus> {
    return apiFetch<WalletSyncStatus>(
      `/user/wallet/sync-status?user_id=${encodeURIComponent(userId)}`,
    );
  },

  importInbox(userId: string): Promise<WalletInboxImportResult> {
    return apiFetch<WalletInboxImportResult>(
      `/user/wallet/import-inbox?user_id=${encodeURIComponent(userId)}`,
      { method: "POST" },
    );
  },
};
