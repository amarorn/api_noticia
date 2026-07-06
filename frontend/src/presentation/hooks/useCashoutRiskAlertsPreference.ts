import { useCallback, useEffect, useState } from "react";
import {
  CASHOUT_RISK_ALERTS_CHANGED,
  readCashoutRiskAlertsEnabled,
  writeCashoutRiskAlertsEnabled,
} from "@/presentation/utils/cashoutAlertStorage";

/** Preferência global de alertas automáticos de risco de cash-out. */
export function useCashoutRiskAlertsPreference() {
  const [riskAlertsEnabled, setRiskAlertsEnabledState] = useState(readCashoutRiskAlertsEnabled);

  const sync = useCallback(() => {
    setRiskAlertsEnabledState(readCashoutRiskAlertsEnabled());
  }, []);

  useEffect(() => {
    sync();
    const onChanged = () => sync();
    window.addEventListener(CASHOUT_RISK_ALERTS_CHANGED, onChanged);
    window.addEventListener("storage", onChanged);
    return () => {
      window.removeEventListener(CASHOUT_RISK_ALERTS_CHANGED, onChanged);
      window.removeEventListener("storage", onChanged);
    };
  }, [sync]);

  const setRiskAlertsEnabled = useCallback((enabled: boolean) => {
    writeCashoutRiskAlertsEnabled(enabled);
    setRiskAlertsEnabledState(enabled);
  }, []);

  return { riskAlertsEnabled, setRiskAlertsEnabled };
}
