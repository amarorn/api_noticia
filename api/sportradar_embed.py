"""Página HTML do widget Sportradar LMT Plus (match.lmtPlus) — mesmo feed Betradar da Superbet."""

from __future__ import annotations

from fastapi.responses import HTMLResponse

from config import settings

# Config alinhada ao tracker lateral da Superbet (sr-lmt-*).
_LMT_PLUS_OPTIONS = """
        layout: 'topdown',
        disableWidgetHeader: true,
        momentum: 'compact',
        scoreboard: 'compact',
        collapseTo: 'disable',
        tabsPosition: 'bottom',
        ballSpottingVisibleLines: 1,
"""


def sportradar_public_config() -> dict[str, str | bool | None]:
    client_id = (settings.sportradar_client_id or "").strip() or None
    return {
        "client_id": client_id,
        "widget": "match.lmtPlus",
        "language": settings.sportradar_language,
        "embed_available": client_id is not None,
    }


def render_lmt_embed_html(*, betradar_id: str) -> str:
    client_id = (settings.sportradar_client_id or "").strip()
    if not client_id:
        return _render_missing_license_html(betradar_id=betradar_id)

    match_id = betradar_id.strip()
    if not match_id.isdigit():
        return _render_error_html("betradar_id inválido — esperado ID numérico Betradar.")

    loader_url = f"https://widgets.sir.sportradar.com/{client_id}/widgetloader"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LMT · Betradar {match_id}</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      background: #060a0e;
      overflow: hidden;
      min-height: 100%;
    }}
    #sr-lmt-root {{
      min-height: 280px;
      width: 100%;
    }}
  </style>
</head>
<body>
  <div id="sr-lmt-root"></div>
  <script type="text/javascript">
    (function(a,b,c,d,e,f,g,h,i){{a[e]||(i=a[e]=function(){{(a[e].q=a[e].q||[]).push(arguments)}},i.l=1*new Date,i.o=f,
    g=b.createElement(c),h=b.getElementsByTagName(c)[0],g.async=1,g.src=d,g.setAttribute("n",e),h.parentNode.insertBefore(g,h)
    )}})(window,document,"script","{loader_url}","SIR", {{
      language: "{settings.sportradar_language}"
    }});

    SIR("addWidget", "#sr-lmt-root", "match.lmtPlus", {{
      matchId: {match_id},
{_LMT_PLUS_OPTIONS}
      onTrack: function(eventType, data) {{
        if (eventType === "data_change" && data && data.error) {{
          console.error("Sportradar LMT:", data.error);
        }}
      }}
    }});
  </script>
</body>
</html>"""


def _render_missing_license_html(*, betradar_id: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{
      margin: 0;
      font-family: system-ui, sans-serif;
      background: #060a0e;
      color: #e2e8f0;
      padding: 1.25rem;
      font-size: 14px;
      line-height: 1.5;
    }}
    code {{ background: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 4px; }}
  </style>
</head>
<body>
  <p><strong>Widget Sportradar indisponível</strong></p>
  <p>Defina <code>SPORTRADAR_CLIENT_ID</code> no <code>.env</code> (licença Betradar/Sportradar).</p>
  <p>Betradar matchId deste jogo: <code>{betradar_id}</code></p>
</body>
</html>"""


def _render_error_html(message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8" /></head>
<body style="margin:0;background:#060a0e;color:#fca5a5;padding:1rem;font-family:system-ui,sans-serif;font-size:14px;">
  <p>{message}</p>
</body></html>"""


def lmt_embed_response(*, betradar_id: str) -> HTMLResponse:
    html = render_lmt_embed_html(betradar_id=betradar_id)
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store",
            "X-Frame-Options": "SAMEORIGIN",
        },
    )
