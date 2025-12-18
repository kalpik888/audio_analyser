# Audio Magic Hub - Microservices Architecture

A production-ready, distributed microservices application for audio transcription, analysis, and data extraction.

## 🏗️ Architecture Overview

```
                          ┌─────────────────┐
                          │   Client/User   │
                          │  (Audio Files)  │
                          └────────┬────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │      API Gateway         │
                    │     (Port 8000)          │
                    │  Orchestrates all        │
                    │  microservices           │
                    └──────────┬───────────────┘
                               │
        ┌──────────────┬───────┼───────┬──────────────┐
        │              │       │       │              │
        ▼              ▼       ▼       ▼              ▼
    ┌────────┐  ┌──────────┐ ┌──────┐ ┌──────────┐ ┌─────────┐
    │Trans-  │  │ Prompt   │ │Extra-│ │Persist- │ │Supabase │
    │cription│  │Management│ │ction │ │ence     │ │Database │
    │Service │  │ Service  │ │Service│ │Service  │ │         │
    │(8001)  │  │(8002)    │ │(8003)│ │(8004)   │ │(Cloud)  │
    └────────┘  └──────────┘ └──────┘ └──────────┘ └─────────┘
```

## 🎯 Microservices

### 1. **Transcription Service** (Port 8001)
- **Responsibility**: Audio transcription and domain/category detection
- **Uses**: Gemini API (Stage 1 LLM call)
- **Endpoints**:
  - `POST /transcribe` - Transcribe and detect domain
  - `GET /health` - Health check

### 2. **Prompt Management Service** (Port 8002)
- **Responsibility**: Domain-category validation and prompt generation
- **Uses**: Gemini API, Supabase
- **Endpoints**:
  - `POST /validate-and-generate` - Validate or generate prompt
  - `GET /domains` - List all known domains
  - `GET /fetch-prompt` - Fetch prompt from database
  - `GET /health` - Health check

### 3. **Extraction Service** (Port 8003)
- **Responsibility**: Domain-specific data extraction and general analysis
- **Uses**: Gemini API (Stage 2 LLM call)
- **Endpoints**:
  - `POST /extract` - Extract data and analyze
  - `GET /health` - Health check

### 4. **Persistence Service** (Port 8004)
- **Responsibility**: Database operations and data storage
- **Uses**: Supabase
- **Endpoints**:
  - `POST /save` - Save call data to database
  - `GET /call/{call_id}` - Retrieve call data
  - `GET /stats` - Get database statistics
  - `GET /health` - Health check

### 5. **API Gateway** (Port 8000)
- **Responsibility**: Orchestrates microservices and provides unified API
- **Uses**: All other services
- **Endpoints**:
  - `POST /api/transcribe/` - Main transcription endpoint
  - `GET /health` - Health check
  - `GET /` - Root endpoint

## 📦 Deployment

### Prerequisites
- Docker & Docker Compose
- Python 3.13+ (for local development)
- Environment variables configured (see `.env`)

### Quick Start with Docker

```bash
# 1. Clone the repository
cd c:\kalpik\audio_magicHub

# 2. Create .env file with your credentials
cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_service_key
llm_model=gemini-2.0-flash

# Service ports
API_GATEWAY_PORT=8000
TRANSCRIPTION_SERVICE_PORT=8001
PROMPT_SERVICE_PORT=8002
EXTRACTION_SERVICE_PORT=8003
PERSISTENCE_SERVICE_PORT=8004

# Service URLs (for docker-compose, use service names)
TRANSCRIPTION_SERVICE_URL=http://transcription-service:8001
PROMPT_SERVICE_URL=http://prompt-service:8002
EXTRACTION_SERVICE_URL=http://extraction-service:8003
PERSISTENCE_SERVICE_URL=http://persistence-service:8004
EOF

# 3. Build and start all services
docker-compose up -d

# 4. Verify services are running
docker-compose ps

# 5. Check health
curl http://localhost:8000/health
```

### Local Development (Without Docker)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Update shared_config.py service URLs to localhost
# Change TRANSCRIPTION_SERVICE_URL=http://localhost:8001
# Change PROMPT_SERVICE_URL=http://localhost:8002
# Change EXTRACTION_SERVICE_URL=http://localhost:8003
# Change PERSISTENCE_SERVICE_URL=http://localhost:8004

# 3. In separate terminals, start each service:

# Terminal 1: Prompt Service (must start first)
cd microservices/prompt_management_service
python main.py

# Terminal 2: Transcription Service
cd microservices/transcription_service
python main.py

# Terminal 3: Extraction Service
cd microservices/extraction_service
python main.py

# Terminal 4: Persistence Service
cd microservices/persistence_service
python main.py

# Terminal 5: API Gateway
cd microservices/api_gateway
python main.py
```

## 🔄 Request Flow

```
1. Client sends audio file to API Gateway (POST /api/transcribe/)
   ↓
2. API Gateway calls Transcription Service
   → Returns: transcription, domain, category, tokens
   ↓
3. API Gateway calls Prompt Service
   → Validates domain-category
   → Generates prompt if needed (and saves async)
   → Returns: custom_prompt or null
   ↓
4. API Gateway calls Extraction Service
   → Extracts domain-specific + general data
   → Returns: extracted_data, general_metrics, tokens
   ↓
5. API Gateway calls Persistence Service
   → Saves to general table (gets call_id)
   → Saves to domain_specific table (with call_id FK)
   → Returns: success status, call_id
   ↓
6. API Gateway aggregates results
   → Returns unified JSON response to client
```

## 📊 Data Flow

### Input
```json
{
  "file": "audio.mp3"
}
```

### Internal Communication (Service-to-Service)
```json
{
  "transcription": "...",
  "domain": "healthcare",
  "category": "appointment_scheduling",
  "custom_prompt": "..."
}
```

### Output
```json
{
  "filename": "audio.mp3",
  "transcription": "...",
  "domain": "healthcare",
  "category": "appointment_scheduling",
  "domain_specific_data": {...},
  "general_metrics": {...},
  "database": {
    "success": true,
    "call_id": 42
  },
  "token_usage": {
    "stage1_transcription_and_detection": {...},
    "stage2_combined_analysis": {...},
    "total": {...}
  }
}
```

## 🛠️ Configuration

### Environment Variables
```
# API Keys
GEMINI_API_KEY=your_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_key

# Service Ports
API_GATEWAY_PORT=8000
TRANSCRIPTION_SERVICE_PORT=8001
PROMPT_SERVICE_PORT=8002
EXTRACTION_SERVICE_PORT=8003
PERSISTENCE_SERVICE_PORT=8004

# Service URLs (for docker-compose)
TRANSCRIPTION_SERVICE_URL=http://transcription-service:8001
PROMPT_SERVICE_URL=http://prompt-service:8002
EXTRACTION_SERVICE_URL=http://extraction-service:8003
PERSISTENCE_SERVICE_URL=http://persistence-service:8004

# Timeouts
SERVICE_TIMEOUT=30
GEMINI_TIMEOUT=60
```

### Shared Configuration
All services import from `shared_config.py`:
- Service ports and URLs
- API keys and credentials
- Default domain-category mappings
- Timeout settings

## 🔗 Inter-Service Communication

Services communicate via HTTP/JSON using `httpx` for async HTTP requests:

```python
# Example: API Gateway calling Transcription Service
response = await call_service(
    TRANSCRIPTION_SERVICE_URL,
    "/transcribe",
    {"file_bytes": file_bytes.hex(), "mime_type": mime_type}
)
```

**Retry Logic**:
- Max 3 retry attempts
- Exponential backoff (2^attempt seconds)
- Timeout: 30 seconds per request

## 📈 Scaling Strategies

### Horizontal Scaling
```bash
# Scale individual services using docker-compose
docker-compose up -d --scale transcription-service=3

# Use load balancer (Nginx, HAProxy) in front:
# - Route to multiple instances of each service
# - Health checks for failover
```

### Vertical Scaling
- Increase resource limits in docker-compose
- Optimize batch processing in services

### Caching
- Add Redis for prompt caching
- Cache domain-category validation

### Load Balancing
```nginx
# Example Nginx config
upstream transcription-services {
    server transcription-service:8001;
    server transcription-service:8002;
    server transcription-service:8003;
}

server {
    listen 80;
    location /transcribe {
        proxy_pass http://transcription-services;
    }
}
```

## 🚀 Production Deployment

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: api-gateway
        image: audio-hub/api-gateway:latest
        ports:
        - containerPort: 8000
        env:
        - name: TRANSCRIPTION_SERVICE_URL
          value: http://transcription-service:8001
        # ... other env vars
```

### AWS/Azure/GCP
1. **Container Registry**: Push Docker images
2. **Orchestration**: ECS, AKS, or GKE
3. **Database**: Managed database for Supabase
4. **Load Balancer**: ALB/AppGW/Cloud Load Balancer
5. **Monitoring**: CloudWatch/Monitor/Stackdriver

## 📝 Logging & Monitoring

### Local Development
```bash
# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f transcription-service
```

### Production
Integrate with:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Datadog** or **New Relic**
- **CloudWatch** (AWS)
- **Application Insights** (Azure)

## ✅ Health Checks

All services expose `/health` endpoint:

```bash
# Check individual services
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

Docker Compose includes automatic health checks with 10s intervals.

## 🔐 Security

### API Gateway
- CORS configured (customizable)
- Input validation on all endpoints
- Error handling with safe messages

### Inter-Service Communication
- Services only accessible within Docker network
- Can add JWT/OAuth between services
- Use service mesh (Istio) in Kubernetes

### Database
- Supabase handles authentication
- Service keys used for backend communication
- Row-level security can be configured

## 🧪 Testing

### Test Individual Services
```bash
# Transcription Service
curl -X POST http://localhost:8001/transcribe \
  -H "Content-Type: application/json" \
  -d '{"file_bytes": "...", "mime_type": "audio/mpeg"}'

# Prompt Service
curl -X POST http://localhost:8002/validate-and-generate \
  -H "Content-Type: application/json" \
  -d '{"domain": "healthcare", "category": "appointment_scheduling"}'
```

### Load Testing
```bash
# Using Apache Bench
ab -n 100 -c 10 -p audio.mp3 http://localhost:8000/api/transcribe/

# Using k6
k6 run load-test.js
```

## 📚 API Documentation

Swagger UI available at:
- **API Gateway**: http://localhost:8000/docs
- **Transcription**: http://localhost:8001/docs
- **Prompt Service**: http://localhost:8002/docs
- **Extraction**: http://localhost:8003/docs
- **Persistence**: http://localhost:8004/docs

## 🐛 Troubleshooting

### Services not connecting
```bash
# Check if services are running
docker-compose ps

# Verify network connectivity
docker network ls
docker network inspect audio-hub-network

# Check service logs
docker-compose logs transcription-service
```

### Database connection issues
```bash
# Verify Supabase credentials in .env
# Test connection manually
python -c "from supabase import create_client; \
create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)"
```

### High latency
- Check Gemini API quotas
- Monitor network latency between services
- Consider adding caching layer
- Profile services with `python -m cProfile`

## 📋 Directory Structure

```
audio_magicHub/
├── microservices/
│   ├── shared_config.py          # Shared configuration
│   ├── service_client.py         # Inter-service communication
│   ├── api_gateway/
│   │   ├── main.py
│   │   └── Dockerfile
│   ├── transcription_service/
│   │   ├── main.py
│   │   └── Dockerfile
│   ├── prompt_management_service/
│   │   ├── main.py
│   │   └── Dockerfile
│   ├── extraction_service/
│   │   ├── main.py
│   │   └── Dockerfile
│   └── persistence_service/
│       ├── main.py
│       └── Dockerfile
├── docker-compose.yml             # Orchestration
├── requirements.txt               # Dependencies
├── .env                          # Environment variables
└── README.md                     # This file
```

## 🔄 Continuous Integration/Deployment

### GitHub Actions Example
```yaml
name: Deploy Microservices

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build and push Docker images
        run: docker-compose build
      - name: Deploy to production
        run: docker stack deploy -c docker-compose.yml audio-hub
```

## 📖 References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [Microservices Patterns](https://microservices.io/)

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📧 Support

For issues and questions:
- Open GitHub Issues
- Check existing documentation
- Review microservices logs

---

**Version**: 2.0.0  
**Last Updated**: December 2025  
**Maintainer**: Audio Magic Hub Team
