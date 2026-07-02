import { useCallback, useEffect, useState } from "react";
import {
  ensureNotificationPermission,
  notificationPermission,
} from "@/presentation/utils/browserNotifications";

export const COPILOT_ALERTS_KEY = "bolao-copilot-alerts-active";
const COPILOT_ALERTS_CHANGED = "copilot-alerts-changed";

export function readCopilotAlertsActive(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(COPILOT_ALERTS_KEY) === "1";
}

export function writeCopilotAlertsActive(active: boolean): void {
  if (typeof window === "undefined") return;
  if (active) {
    window.localStorage.setItem(COPILOT_ALERTS_KEY, "1");
  } else {
    window.localStorage.removeItem(COPILOT_ALERTS_KEY);
  }
  window.dispatchEvent(new Event(COPILOT_ALERTS_CHANGED));
}

/** Preferência de alertas do copiloto — sincroniza entre painel e hook de notificações. */
export function useCopilotAlertsPreference() {
  const [alertsActive, setAlertsActiveState] = useState(readCopilotAlertsActive);
  const [notifyPermission, setNotifyPermission] = useState(notificationPermission());

  const syncAlerts = useCallback(() => {
    setAlertsActiveState(readCopilotAlertsActive());
  }, []);

  const refreshPermission = useCallback(() => {
    setNotifyPermission(notificationPermission());
    syncAlerts();
  }, [syncAlerts]);

  useEffect(() => {
    refreshPermission();
    const onVisible = () => {
      if (document.visibilityState === "visible") refreshPermission();
    };
    const onAlertsChanged = () => syncAlerts();
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener(COPILOT_ALERTS_CHANGED, onAlertsChanged);
    window.addEventListener("storage", onAlertsChanged);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener(COPILOT_ALERTS_CHANGED, onAlertsChanged);
      window.removeEventListener("storage", onAlertsChanged);
    };
  }, [refreshPermission, syncAlerts]);

  const activateAlerts = useCallback(async () => {
    const ok = await ensureNotificationPermission();
    const current = notificationPermission();
    setNotifyPermission(current);
    if (ok && current === "granted") {
      writeCopilotAlertsActive(true);
      setAlertsActiveState(true);
    }
  }, []);

  const deactivateAlerts = useCallback(() => {
    writeCopilotAlertsActive(false);
    setAlertsActiveState(false);
  }, []);

  return {
    alertsActive,
    notifyPermission,
    activateAlerts,
    deactivateAlerts,
    refreshPermission,
  };
}
