# TODO (task 1): write a production Dockerfile for this app. Build context is this folder.
#   - multi-stage: a "builder" stage that pip-installs requirements.txt, and a slim runtime stage
#   - base image pinned to a version tag (e.g. python:3.12-slim-bookworm), never :latest
#   - copy requirements.txt and install BEFORE copying the source (layer cache)
#   - run as a non-root user, HEALTHCHECK on /health, exec-form CMD running uvicorn on 0.0.0.0:8000
#   - ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1, pip install --no-cache-dir, EXPOSE 8000
# Check yourself any time with:  python -m lab   (run from the starter/ folder)
