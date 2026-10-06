# syntax=docker/dockerfile:1
#
# The AURA backend (FastAPI + Whisper + Piper) as one container.
#
#   docker build -t aura-backend .                      (from the Aurora/ folder)
#   docker run -p 8000:8000 --env-file .env aura-backend
#
# What is inside, so nothing is downloaded when the container starts:
#   * the six companion Piper voices plus the two accent voices behind the regional speaking
#     styles (~550 MB), fetched by scripts/download_voices.py
#   * the Whisper base.en model (~150 MB) — skip it with --build-arg BAKE_WHISPER=false
#     if you will use STT_PROVIDER=groq (the image is then ~150 MB smaller)
#
# On start it applies database migrations (set RUN_MIGRATIONS=false to skip, e.g. when
# several replicas start at once and a release step migrates instead), then serves on
# $PORT (default 8000). It needs the same environment variables as a local run: at least
# GROQ_API_KEY, DATABASE_URL and JWT_SECRET. See the README ("Deploying") and .env.example.
#
# Memory (measured with docker stats, one learner): ~0.75 GB right after start-up with local Whisper and
# the six companion voices (~0.85 GB once a turn has run); ~0.65 GB with STT_PROVIDER=groq; ~0.1-0.2 GB with
# STT_PROVIDER=groq and PREWARM_MODELS=false (each voice, ~90 MB, then loads on first use). The two accent
# voices load on first use and add ~100 MB and ~125 MB. The image is ~0.9 GB to pull, ~1.45 GB unpacked.
# Verify a build with: python scripts/smoke_container.py

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    ENVIRONMENT=production

# The platform's proxy sits in front of the container, so trust its X-Forwarded-For:
# without this every learner would share the proxy's address, and so one rate-limit
# bucket. Only safe because the container isn't reachable except through that proxy.
ENV FORWARDED_ALLOW_IPS=*

WORKDIR /app
RUN useradd --create-home --uid 10001 aura && chown aura:aura /app

# Layers are ordered by how rarely they change, so a rebuild only redoes what it must:
#   1. the voices (~550 MB)         change only if the voice list does
#   2. the Python packages          change when requirements.txt does
#   3. the Whisper model (~150 MB)  needs the packages, so it follows them
#   4. the application code         changes constantly
# The files in 1 and 3 are created by the unprivileged user, so they are its own already
# (a recursive chown afterwards would copy the models into a second, equally large layer).

# 1. Voices. The downloader needs only the voice list, which is plain data in personalities.py.
USER aura
COPY --chown=aura:aura backend/__init__.py backend/__init__.py
COPY --chown=aura:aura backend/personalities.py backend/personalities.py
COPY --chown=aura:aura scripts/download_voices.py scripts/download_voices.py
RUN python scripts/download_voices.py

# 2. Packages (installed system-wide, so as root)
USER root
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

# 3. Whisper
USER aura
ARG BAKE_WHISPER=true
ARG WHISPER_MODEL_SIZE=base.en
RUN if [ "$BAKE_WHISPER" = "true" ]; then \
        python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL_SIZE}', device='cpu', compute_type='int8')"; \
    fi

# 4. The application
COPY --chown=aura:aura backend/ backend/

EXPOSE 8000

# /health answers 503 when the database is unreachable, the schema is behind, or no voice
# is installed. The start period covers loading the models.
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD python -c "import os, urllib.request as u; u.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=8)"

CMD ["sh", "-c", "if [ \"${RUN_MIGRATIONS:-true}\" = \"true\" ]; then alembic -c backend/alembic.ini upgrade head; fi && exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
