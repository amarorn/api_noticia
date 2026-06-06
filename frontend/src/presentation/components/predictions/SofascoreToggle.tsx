interface SofascoreToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  eventId: string;
  onEventIdChange: (value: string) => void;
  disabled?: boolean;
  hint?: string;
}

export function SofascoreToggle({
  enabled,
  onChange,
  eventId,
  onEventIdChange,
  disabled = false,
  hint,
}: SofascoreToggleProps) {
  return (
    <div className="space-y-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
      <label className="flex cursor-pointer items-start gap-3">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
          className="mt-0.5 h-4 w-4 rounded border-white/20 bg-transparent accent-neon-green"
        />
        <span>
          <span className="block text-sm font-medium text-white">
            Enriquecer com escalação Sofascore
          </span>
          <span className="mt-0.5 block text-xs text-slate-500">
            Preenche FEPT (formações + notas) no motor KXL
          </span>
        </span>
      </label>

      {enabled && (
        <div>
          <label htmlFor="sofascore-event-id" className="mb-1.5 block text-xs font-medium text-slate-400">
            ID do evento (opcional)
          </label>
          <input
            id="sofascore-event-id"
            type="text"
            inputMode="numeric"
            placeholder="Ex.: 11774480 — vazio = busca automática"
            value={eventId}
            onChange={(e) => onEventIdChange(e.target.value.replace(/\D/g, ""))}
            className="select-field"
          />
          {hint && <p className="mt-1.5 text-[11px] text-slate-500">{hint}</p>}
        </div>
      )}
    </div>
  );
}
