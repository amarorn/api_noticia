import { motion } from "framer-motion";
import { IconBell, IconCheck } from "@/presentation/components/ui/Icons";
import { CASHOUT_APPROACH_RATIO } from "@/presentation/utils/cashoutAlertStorage";

export { CASHOUT_APPROACH_RATIO };

export interface CashoutAlertDraftFields {
  stake: number;
  oddsPlaced: number;
  offeredCashout: number | null;
  cashoutAlertEnabled: boolean;
  cashoutAlertTarget: number | null;
  cashoutNotifyApproach: boolean;
  cashoutNotifyReach: boolean;
}

interface CashoutAlertSetupProps {
  draft: CashoutAlertDraftFields;
  notifyPermission: NotificationPermission | "unsupported";
  refreshSeconds: number;
  onDraftChange: (patch: Partial<CashoutAlertDraftFields>) => void;
  onRequestNotificationPermission: () => void | Promise<void>;
}

function formatBrl(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function buildPresets(stake: number, oddsPlaced: number) {
  const potential = stake * oddsPlaced;
  return [
    { id: "stake", label: "Recuperar stake", hint: "Volta ao zero a zero", value: stake },
    {
      id: "profit10",
      label: "+10% lucro",
      hint: "Pequena margem",
      value: Math.round(stake * 1.1 * 100) / 100,
    },
    {
      id: "half",
      label: "Metade do prêmio",
      hint: "50% do ganho potencial",
      value: Math.round(potential * 0.5 * 100) / 100,
    },
    {
      id: "full",
      label: "Prêmio cheio",
      hint: "Ganho máximo",
      value: Math.round(potential * 100) / 100,
    },
  ];
}

function StepBadge({ n, label, done }: { n: number; label: string; done?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
          done
            ? "bg-neon-green/20 text-neon-green ring-1 ring-neon-green/40"
            : "bg-white/10 text-slate-400 ring-1 ring-white/15"
        }`}
      >
        {done ? <IconCheck className="h-3.5 w-3.5" /> : n}
      </span>
      <span className={`text-xs font-medium ${done ? "text-neon-green" : "text-slate-400"}`}>
        {label}
      </span>
    </div>
  );
}

export function CashoutAlertSetup({
  draft,
  notifyPermission,
  refreshSeconds,
  onDraftChange,
  onRequestNotificationPermission,
}: CashoutAlertSetupProps) {
  const potential = draft.stake * draft.oddsPlaced;
  const presets = buildPresets(draft.stake, draft.oddsPlaced);
  const target = draft.cashoutAlertTarget;
  const hasTarget = target != null && target > 0;
  const notificationsOn = notifyPermission === "granted";

  return (
    <div className="overflow-hidden rounded-2xl border border-amber-500/25 bg-gradient-to-br from-amber-500/[0.08] via-transparent to-orange-500/[0.04]">
      <div className="border-b border-amber-500/15 px-4 py-3 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/15 text-amber-300">
              <IconBell className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-white">Cash-out & alertas</h3>
              <p className="text-[11px] text-slate-400">
                Valor na Superbet agora + meta para avisar quando chegar perto
              </p>
            </div>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={draft.cashoutAlertEnabled}
            aria-label="Ativar alertas de cash-out"
            onClick={() =>
              onDraftChange({
                cashoutAlertEnabled: !draft.cashoutAlertEnabled,
                cashoutAlertTarget:
                  !draft.cashoutAlertEnabled && !hasTarget
                    ? Math.round(potential * 0.5 * 100) / 100
                    : draft.cashoutAlertTarget,
              })
            }
            className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${
              draft.cashoutAlertEnabled ? "bg-amber-400/80" : "bg-white/15"
            }`}
          >
            <span
              className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform ${
                draft.cashoutAlertEnabled ? "translate-x-5" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>
      </div>

      <div className="border-b border-white/5 px-4 py-3 sm:px-5">
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Cash-out oferecido agora (Superbet)
          </span>
          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2">
            <span className="text-sm text-slate-500">R$</span>
            <input
              type="number"
              min={0}
              step={0.01}
              placeholder="ex.: 4,31"
              value={draft.offeredCashout ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                onDraftChange({
                  offeredCashout: raw === "" ? null : Number(raw),
                });
              }}
              className="w-full bg-transparent font-mono text-base font-semibold text-neon-green outline-none placeholder:text-slate-600"
            />
          </div>
          <span className="text-[10px] text-slate-500">
            Com ticket da extensão, atualiza automaticamente a cada {refreshSeconds}s
          </span>
        </label>
      </div>

      {draft.cashoutAlertEnabled && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="space-y-5 px-4 py-4 sm:px-5"
        >
          <div className="flex flex-wrap gap-4 sm:gap-6">
            <StepBadge n={1} label="Cash-out atual" done={draft.offeredCashout != null} />
            <StepBadge n={2} label="Sua meta" done={hasTarget} />
            <StepBadge n={3} label="Notificações" done={notificationsOn} />
          </div>

          <label className="flex flex-col gap-1.5 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-200/70">
              Meta para alertar
            </span>
            <div className="flex items-center gap-2">
              <span className="text-sm text-amber-200/60">R$</span>
              <input
                type="number"
                min={0}
                step={0.01}
                placeholder="15,00"
                value={draft.cashoutAlertTarget ?? ""}
                onChange={(e) => {
                  const raw = e.target.value;
                  onDraftChange({
                    cashoutAlertTarget: raw === "" ? null : Number(raw),
                  });
                }}
                className="w-full bg-transparent font-mono text-lg font-semibold text-white outline-none placeholder:text-slate-600"
              />
            </div>
            {hasTarget && draft.offeredCashout != null && draft.offeredCashout > 0 && (
              <span className="text-[10px] text-amber-200/80">
                Faltam {formatBrl(Math.max(0, target - draft.offeredCashout))} para a meta
              </span>
            )}
          </label>

          <div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Atalhos rápidos
            </p>
            <div className="flex flex-wrap gap-2">
              {presets.map((p) => {
                const active = hasTarget && Math.abs(target - p.value) < 0.02;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() =>
                      onDraftChange({ cashoutAlertTarget: p.value, cashoutAlertEnabled: true })
                    }
                    className={`rounded-xl border px-3 py-2 text-left transition-all ${
                      active
                        ? "border-amber-400/50 bg-amber-500/15 ring-1 ring-amber-400/30"
                        : "border-white/10 bg-white/[0.03] hover:border-amber-400/30 hover:bg-amber-500/10"
                    }`}
                  >
                    <span className="block text-xs font-semibold text-white">{p.label}</span>
                    <span className="block font-mono text-[11px] text-amber-200/90">
                      {formatBrl(p.value)}
                    </span>
                    <span className="block text-[10px] text-slate-500">{p.hint}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <AlertTypeCard
              title="Quase lá"
              subtitle={`Aviso aos ${Math.round(CASHOUT_APPROACH_RATIO * 100)}% da meta`}
              example={
                hasTarget
                  ? `Quando cash-out ≥ ${formatBrl(target * CASHOUT_APPROACH_RATIO)}`
                  : "Defina a meta acima"
              }
              active={draft.cashoutNotifyApproach}
              onClick={() =>
                onDraftChange({ cashoutNotifyApproach: !draft.cashoutNotifyApproach })
              }
              tone="approach"
            />
            <AlertTypeCard
              title="Meta batida"
              subtitle="Cash-out atingiu ou passou"
              example={hasTarget ? `Quando cash-out ≥ ${formatBrl(target)}` : "Defina a meta acima"}
              active={draft.cashoutNotifyReach}
              onClick={() => onDraftChange({ cashoutNotifyReach: !draft.cashoutNotifyReach })}
              tone="reach"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-3">
            <div>
              <p className="text-xs font-medium text-white">Notificações do navegador</p>
              <p className="text-[10px] text-slate-500">
                {notificationsOn
                  ? "Ativas — você será avisado mesmo com a aba em segundo plano"
                  : "Clique para permitir alertas sonoros e pop-up"}
              </p>
            </div>
            <button
              type="button"
              onClick={() => void onRequestNotificationPermission()}
              className={`shrink-0 rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
                notificationsOn
                  ? "border border-neon-green/40 bg-neon-green/15 text-neon-green"
                  : "border border-amber-400/40 bg-amber-500/20 text-amber-100 hover:bg-amber-500/30"
              }`}
            >
              {notificationsOn ? (
                <span className="inline-flex items-center gap-1.5">
                  <IconCheck className="h-3.5 w-3.5" /> Ativas
                </span>
              ) : (
                "Ativar alertas"
              )}
            </button>
          </div>
        </motion.div>
      )}

      {!draft.cashoutAlertEnabled && (
        <p className="px-4 pb-4 text-xs text-slate-500 sm:px-5">
          Ative o interruptor acima para monitorar um valor de saída e receber avisos automáticos.
        </p>
      )}
    </div>
  );
}

function AlertTypeCard({
  title,
  subtitle,
  example,
  active,
  onClick,
  tone,
}: {
  title: string;
  subtitle: string;
  example: string;
  active: boolean;
  onClick: () => void;
  tone: "approach" | "reach";
}) {
  const activeStyles =
    tone === "approach"
      ? "border-amber-400/40 bg-amber-500/10 ring-1 ring-amber-400/25"
      : "border-neon-green/40 bg-neon-green/10 ring-1 ring-neon-green/25";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border p-3 text-left transition-all ${
        active ? activeStyles : "border-white/10 bg-white/[0.02] hover:border-white/20"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-white">{title}</p>
          <p className="text-[11px] text-slate-400">{subtitle}</p>
        </div>
        <span
          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
            active
              ? tone === "reach"
                ? "border-neon-green/50 bg-neon-green/20 text-neon-green"
                : "border-amber-400/50 bg-amber-500/20 text-amber-200"
              : "border-white/15 bg-white/5 text-transparent"
          }`}
        >
          <IconCheck className="h-3 w-3" />
        </span>
      </div>
      <p className="mt-2 font-mono text-[10px] text-slate-500">{example}</p>
    </button>
  );
}
