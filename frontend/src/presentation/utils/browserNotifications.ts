/** Notificações nativas do browser + fallback via extensão Chrome. */

export type CashoutAlertKind = "approach" | "reach";

export interface CashoutAlertPayload {
  betId: string;
  title: string;
  body: string;
  kind: CashoutAlertKind;
  currentValue: number;
  targetValue: number;
}

const EXTENSION_MSG = "BOLAO_CASHOUT_ALERT";

export async function ensureNotificationPermission(): Promise<boolean> {
  if (typeof Notification === "undefined") return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const result = await Notification.requestPermission();
  return result === "granted";
}

export function notificationPermission(): NotificationPermission | "unsupported" {
  if (typeof Notification === "undefined") return "unsupported";
  return Notification.permission;
}

function notifyViaExtension(payload: CashoutAlertPayload): void {
  window.postMessage(
    {
      source: "bolao-ai-app",
      type: EXTENSION_MSG,
      payload,
    },
    window.location.origin,
  );
}

export function showCashoutAlert(payload: CashoutAlertPayload): void {
  notifyViaExtension(payload);

  if (typeof Notification === "undefined" || Notification.permission !== "granted") {
    return;
  }

  const tag = `bolao-cashout-${payload.betId}-${payload.kind}`;
  try {
    new Notification(payload.title, {
      body: payload.body,
      tag,
      icon: "/favicon.ico",
    });
  } catch {
    /* ignore — Safari/iOS podem falhar silenciosamente */
  }
}
