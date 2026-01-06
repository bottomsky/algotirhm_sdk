FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV SERVICE_BIND_HOST=0.0.0.0

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv pip sync --system uv.lock

COPY src ./src
COPY scripts ./scripts

RUN chmod +x scripts/run_algo_core_service.sh

EXPOSE 8000

CMD ["sh", "scripts/run_algo_core_service.sh"]
