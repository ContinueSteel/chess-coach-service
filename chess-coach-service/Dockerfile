# Backend Dockerfile for Chess Coach Service
# Uses Python and installs Stockfish engine

FROM python:3.12-slim

# Install system dependencies, including Stockfish
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        stockfish \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY chess-coach-service/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY chess-coach-service/backend/ ./

EXPOSE 8000

# Start FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]