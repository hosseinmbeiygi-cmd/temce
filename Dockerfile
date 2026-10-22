FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

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
