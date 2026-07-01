# Multi-stage build: the frontend (Node) is compiled to static assets, then
# copied into the backend (Python) image, which serves both the API and the
# built UI from a single origin (see dataset_insight/api/main.py).

FROM node:24-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY dataset_insight/ ./dataset_insight/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000
CMD ["sh", "-c", "uvicorn dataset_insight.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
