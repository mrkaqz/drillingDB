FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# DATA_DIR is the single volume mount point for db, uploads, and exports
ENV DATA_DIR=/data

EXPOSE 7000

# Run migrations then start the server
CMD ["sh", "-c", "alembic upgrade head && uvicorn drilling_app.main:app --host 0.0.0.0 --port 7000 --app-dir src"]
