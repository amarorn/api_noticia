/**
 * Extrai event_id Superbet de URLs BR (.bet.br) e legado (/event/123).
 */
(function () {
  "use strict";

  function extractSuperbetEventId(loc = location) {
    const hay = loc.href;
    const patterns = [
      /\/(?:event|evento)\/(\d+)/i,
      /\/e-(\d+)/i,
      /[?&]event(?:Id|_id)=(\d+)/i,
      /#\/(?:event|evento)\/(\d+)/i,
      // superbet.bet.br/odds/futebol/time-a-x-time-b-13367973
      /\/odds\/(?:[^?#]+\/)*[^/?#]+-(\d{5,})(?:\?|#|$)/i,
    ];
    for (const p of patterns) {
      const m = hay.match(p);
      if (m) return parseInt(m[1], 10);
    }
    const seg = loc.pathname.split("/").filter(Boolean).pop() || "";
    const slug = seg.match(/-(\d{5,})$/);
    if (slug) return parseInt(slug[1], 10);
    return null;
  }

  window.bolaoExtractSuperbetEventId = extractSuperbetEventId;
})();
