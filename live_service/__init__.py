"""live_service: microsserviço FastAPI independente para apostas in-play.

Pode ser executado standalone (python -m live_service) na porta 8001,
ou montado dentro de api/main.py via include_router() para compatibilidade.

Separação de responsabilidades:
  api/main.py   → modelos pré-jogo, notícias, histórico
  live_service/ → captura ao vivo, advice, cashout, bilhetes otimizados

Plano de migração:
  Fase 1 (atual): live_service roda standalone na porta 8001
  Fase 2: api/main.py inclui live_router (mesmos endpoints, sem duplicação)
  Fase 3: rotas /worldcup/superbet/live/* removidas de api/main.py
"""
