FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared config
COPY microservices/shared_config.py ./
COPY microservices/service_client.py ./

# Copy API Gateway code
COPY microservices/api_gateway/main.py ./main.py

# Expose port
EXPOSE 8000

# Run API Gateway
CMD ["python", "main.py"]
