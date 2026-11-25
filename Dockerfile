# One image for both Python apps. docker-compose.yml picks which one each container runs.
FROM python:3.12-slim

WORKDIR /app

# Install libraries first, so Docker reuses this step when only the code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hub ./hub
COPY dashboard ./dashboard
COPY data ./data
