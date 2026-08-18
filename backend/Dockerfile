# Dockerfile de DESENVOLVIMENTO — não use em produção
FROM python:3.12-slim

WORKDIR /app

# Instala dependências antes de copiar o código (cache de layers)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

# Hot reload habilitado via volume mount no docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
