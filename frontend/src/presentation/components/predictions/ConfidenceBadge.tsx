import type { OutcomeLabel } from "@/domain/entities";
import {
  confidenceColor,
  confidenceLevel,
  formatPercent,
  outcomeColors,
  outcomeLabels,
} from "@/presentation/theme";

interface ConfidenceBadgeProps {
  confidence: number;
  prediction: OutcomeLabel;
}

export function ConfidenceBadge({ confidence, prediction }: ConfidenceBadgeProps) {
  const level = confidenceLevel(confidence);
  const color = confidenceColor(level);

  return (
    <div className="flex items-center gap-3">
      <div
        className="flex h-12 w-12 items-center justify-center rounded-xl text-xl font-bold"
        style={{
          backgroundColor: `${outcomeColors[prediction]}20`,
          color: outcomeColors[prediction],
          boxShadow: `0 0 16px ${outcomeColors[prediction]}30`,
        }}
      >
        {prediction}
      </div>
      <div>
        <p className="text-xs uppercase tracking-wider text-slate-500">Confiança</p>
        <p className="text-lg font-bold" style={{ color }}>
          {formatPercent(confidence)}
        </p>
        <p className="text-xs text-slate-400">{outcomeLabels[prediction]}</p>
      </div>
    </div>
  );
}

interface ConfidenceBarProps {
  confidence: number;
}

export function ConfidenceBar({ confidence }: ConfidenceBarProps) {
  const level = confidenceLevel(confidence);
  const color = confidenceColor(level);

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-500">
        <span>Confiança do modelo</span>
        <span style={{ color }}>{formatPercent(confidence)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${Math.min(confidence * 100, 100)}%`,
            background: `linear-gradient(90deg, ${color}88, ${color})`,
          }}
        />
      </div>
    </div>
  );
}
