FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir . && \
    useradd -m -u 1000 plexbud

USER plexbud

ENTRYPOINT ["plexbud"]
