/**
 * MAIN world — escuta Bac Bo sem quebrar instanceof WebSocket (Evolution exige).
 */
(function () {
  "use strict";

  if (window.__bolaoBacboWsPatched) return;

  const NativeWS = window.WebSocket;
  if (!NativeWS) return;

  const BACBO_RE = /bacbo\/player\/game\/([^/?]+)\/socket/i;

  function tableId(url) {
    const m = String(url || "").match(BACBO_RE);
    return m ? m[1] : null;
  }

  function attachBacboTap(ws, urlStr) {
    if (ws.__bolaoBacboTap) return;
    ws.__bolaoBacboTap = true;
    ws.addEventListener("message", (ev) => {
      if (typeof ev.data !== "string") return;
      const text = ev.data.trim();
      if (!text || (text[0] !== "{" && text[0] !== "[")) return;
      window.postMessage(
        {
          source: "bolao-bacbo-hook",
          type: "BACBO_WS_MESSAGE",
          wsUrl: urlStr,
          tableId: tableId(urlStr),
          data: text,
        },
        "*",
      );
    });
    console.info("[Bolão AI] Bac Bo WS monitor:", tableId(urlStr));
  }

  try {
    class BolaoWebSocket extends NativeWS {
      constructor(url, protocols) {
        const urlStr = String(url || "");
        if (protocols === undefined) {
          super(url);
        } else {
          super(url, protocols);
        }
        if (BACBO_RE.test(urlStr)) {
          attachBacboTap(this, urlStr);
        }
      }
    }

    for (const k of ["CONNECTING", "OPEN", "CLOSING", "CLOSED"]) {
      Object.defineProperty(BolaoWebSocket, k, {
        value: NativeWS[k],
        configurable: true,
      });
    }

    BolaoWebSocket.prototype = NativeWS.prototype;
    window.WebSocket = BolaoWebSocket;
    window.__bolaoBacboWsPatched = true;
  } catch (err) {
    /* Fallback: só tap no prototype — não substitui construtor */
    const nativeAdd = NativeWS.prototype.addEventListener;
    NativeWS.prototype.addEventListener = function (type, listener, options) {
      const ret = nativeAdd.call(this, type, listener, options);
      if (type === "message" && BACBO_RE.test(String(this.url || ""))) {
        attachBacboTap(this, String(this.url));
      }
      return ret;
    };
    window.__bolaoBacboWsPatched = true;
    console.warn("[Bolão AI] Bac Bo hook fallback (prototype):", err);
  }
})();
