FROM node:20-alpine AS frontend-builder
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY index.html ./
COPY metadata.json ./
COPY tsconfig.json ./
COPY vite.config.ts ./
COPY src ./src
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FRONTEND_DIST_DIR=/app/frontend_dist
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY --from=frontend-builder /app/dist /app/frontend_dist

EXPOSE 8000
CMD ["uvicorn", "main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000"]
