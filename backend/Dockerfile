FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user — the app doesn't need root, and running the API
# process as root inside the container is unnecessary blast-radius (V2 core
# build security hardening pass, docs/SECURITY.md).
RUN useradd --create-home --uid 1000 oceanguardian && chown -R oceanguardian:oceanguardian /app
USER oceanguardian

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# seed.py only creates the demo operator account when SEED_DEMO_DATA=true
# is explicitly set (see seed.py) — safe to run unconditionally here since
# the sensitive part is self-gated, not gated by this CMD.
CMD ["sh", "-c", "alembic upgrade head && python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
