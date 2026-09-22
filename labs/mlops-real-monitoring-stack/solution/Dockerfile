# syntax=docker/dockerfile:1
# Build context is the lab root (see docker-compose.yml: app.build.context == ".").

# ---- stage 1: build the dependency tree (compilers / pip cache stay in this stage) ----
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
# Only the three runtime deps the app needs inside the container - not pytest/requests, which stay
# on the host running the tests.
RUN printf 'fastapi>=0.110\nuvicorn>=0.29\npydantic>=2.0\nprometheus-client>=0.19\n' > requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- stage 2: small runtime image ----
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /srv
COPY --from=builder /install /usr/local
COPY solution/lab ./lab
USER app
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "lab.app:app", "--host", "0.0.0.0", "--port", "8000"]
