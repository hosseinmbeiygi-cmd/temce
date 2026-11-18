FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.lock ./
RUN pip install --no-cache-dir --no-deps -r requirements.lock

RUN addgroup --system app && adduser --system --ingroup app --home /app --disabled-password app

COPY pyproject.toml alembic.ini ./
COPY json/*.json ./json/
COPY apps/ ./apps/
COPY backtesting/ ./backtesting/
COPY brsapi/ ./brsapi/
COPY config/ ./config/
COPY contracts/ ./contracts/
COPY core/ ./core/
COPY domain/ ./domain/
COPY ingestion/ ./ingestion/
COPY integrations/ ./integrations/
COPY jobs/ ./jobs/
COPY migrations/ ./migrations/
COPY ml/ ./ml/
COPY models/ ./models/
COPY monitoring/ ./monitoring/
COPY orchestration/ ./orchestration/
COPY providers/ ./providers/
COPY repositories/ ./repositories/
COPY schemas/ ./schemas/
COPY services/ ./services/
COPY src/ ./src/
COPY *.py ./

RUN chown -R app:app /app
USER app

CMD ["python", "-m", "ingestion.main"]
