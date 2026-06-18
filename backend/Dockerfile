# ReviewPulse AI backend (Phase 7 deploy).
FROM python:3.12-slim

WORKDIR /app

# onnxruntime (via fastembed) and scikit-learn need OpenMP at runtime; the slim
# image doesn't ship it, which otherwise crashes embedding/clustering with a
# missing libgomp.so.1.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts

ENV PORT=8000
EXPOSE 8000

# Render/Railway inject $PORT; default 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
