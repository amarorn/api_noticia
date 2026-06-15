import { useEffect, useRef, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import {
  detectLiveRecalibration,
  type LiveRecalibrationEvent,
} from "@/presentation/utils/liveRecalibration";

const DISPLAY_MS = 28_000;

export function useLiveRecalibration(
  data: SuperbetLiveAdvice | undefined,
  isFetching: boolean,
): LiveRecalibrationEvent | null {
  const previousRef = useRef<SuperbetLiveAdvice | null>(null);
  const [event, setEvent] = useState<LiveRecalibrationEvent | null>(null);

  useEffect(() => {
    if (!data || isFetching) return;

    const previous = previousRef.current;
    if (previous) {
      const detected = detectLiveRecalibration(previous, data);
      if (detected) {
        setEvent(detected);
      }
    }

    previousRef.current = data;
  }, [data, isFetching]);

  useEffect(() => {
    if (!event) return;
    const id = window.setTimeout(() => setEvent(null), DISPLAY_MS);
    return () => window.clearTimeout(id);
  }, [event]);

  return event;
}
