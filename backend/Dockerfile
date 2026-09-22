# Dockerfile de DESENVOLVIMENTO — não use em produção
FROM python:3.12-slim

WORKDIR /app

# Instala dependências antes de copiar o código (cache de layers)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

# Hot reload habilitado via volume mount no docker-compose.
#
# --timeout-graceful-shutdown existe por causa do SSE: o uvicorn espera as
# respostas em curso terminarem ANTES de rodar o shutdown do lifespan, e é no
# lifespan que avisamos os streams para encerrarem. Um stream aberto trava o
# desligamento esperando um sinal que só viria depois dele. O teto quebra o
# impasse; ver app/api/events_router.py.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--timeout-graceful-shutdown", "5"]
