FROM python:3.12-slim

WORKDIR /app

# Install the housemktanalyzr package from project root
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Install backend dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend/app/ app/

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
