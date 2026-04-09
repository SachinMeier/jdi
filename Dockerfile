FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY configs /app/configs
COPY scripts /app/scripts
COPY docs /app/docs
COPY systemd /app/systemd

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install .

ENTRYPOINT ["jdi"]
CMD ["--help"]
