# syntax=docker/dockerfile:1

# ---- stage 1: "builder" - trains the model and installs the dependency tree ----
FROM python:3.12-slim-bookworm AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
# Copy ONLY requirements first: this layer (and the install below) is reused from Docker's cache
# until requirements.txt changes, not every time application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY train_model.py .
# Trains on the iris dataset bundled inside scikit-learn - no network access needed to build this
# image. The artifact this writes (model/model.joblib) is the ONLY thing the runtime stage copies
# out of this stage; scikit-learn's own copy of the dataset and this training script never ship.
RUN python train_model.py

# ---- stage 2: small runtime image, only what's needed to SERVE the model ----
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_PATH=/srv/model/model.joblib
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /srv
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build/model ./model
COPY app ./app
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
