import { useRef } from "react";

/**
 * Guarda o valor anterior de `value`, atualizando apenas quando `changeKey` muda
 * (ex.: `data.capturedAt`). Usado para deltas "vs poll anterior" nos KPIs da V2 —
 * sem isso, cada re-render (troca de aba, etc.) apagaria a comparação real.
 *
 * `hold=true` impede que o valor atual vire baseline — necessário enquanto a tela
 * ainda mostra o snapshot leve (fallback de scoreTick) e não o advice completo:
 * sem isso, a primeira captura real seria comparada contra o fallback e geraria
 * um delta falso (ex.: "confiança +38pp") assim que o advice completo chegasse.
 */
export function usePreviousOnChange<T>(value: T, changeKey: unknown, hold = false): T | null {
  const ref = useRef<{ key: unknown; current: T; previous: T | null; initialized: boolean }>({
    key: changeKey,
    current: value,
    previous: null,
    initialized: false,
  });

  if (hold) {
    return null;
  }

  if (!ref.current.initialized) {
    ref.current.initialized = true;
    ref.current.key = changeKey;
    ref.current.current = value;
    return null;
  }

  if (changeKey !== ref.current.key) {
    ref.current.previous = ref.current.current;
    ref.current.current = value;
    ref.current.key = changeKey;
  }

  return ref.current.previous;
}
