import { useCallback, useEffect, useState } from "react";
import {
  CASHOUT_AUTO_EXECUTE_CHANGED,
  readCashoutAutoExecuteConfig,
  writeCashoutAutoExecuteConfig,
  type CashoutAutoExecuteConfig,
} from "@/presentation/utils/cashoutAlertStorage";

export function useCashoutAutoExecutePreference() {
  const [config, setConfigState] = useState(readCashoutAutoExecuteConfig);

  const sync = useCallback(() => {
    setConfigState(readCashoutAutoExecuteConfig());
  }, []);

  useEffect(() => {
    sync();
    const onChanged = () => sync();
    window.addEventListener(CASHOUT_AUTO_EXECUTE_CHANGED, onChanged);
    window.addEventListener("storage", onChanged);
    return () => {
      window.removeEventListener(CASHOUT_AUTO_EXECUTE_CHANGED, onChanged);
      window.removeEventListener("storage", onChanged);
    };
  }, [sync]);

  const updateConfig = useCallback((patch: Partial<CashoutAutoExecuteConfig>) => {
    const next = writeCashoutAutoExecuteConfig(patch);
    setConfigState(next);
    return next;
  }, []);

  return { config, updateConfig };
}
