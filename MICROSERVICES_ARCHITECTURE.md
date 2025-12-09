# Microservices Architecture Documentation

## System Architecture

### Complete Service Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  CLIENTS                                    │
│                    (Postman, Frontend, Mobile Apps)                         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │ HTTP/JSON
                                       │
                    ┌──────────────────▼────────────────────┐
                    │     API GATEWAY (Port 8000)           │
                    │                                       │
                    │  ┌─────────────────────────────────┐  │
                    │  │ POST /api/transcribe/           │  │
                    │  │ Orchestrates entire pipeline    │  │
                    │  └─────────────────────────────────┘  │
                    │  ┌─────────────────────────────────┐  │
                    │  │ GET /health                     │  │
                    │  │ GET /                           │  │
                    │  └─────────────────────────────────┘  │
                    │                                       │
                    └────────────┬───────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         │                       │                       │
    ┌────▼────┐  ┌──────────┐  ┌▼──────┐  ┌──────────┐
    │ Trans-  │  │ Prompt   │  │Extra- │  │Persist- │
    │cription │  │Management│  │ction  │  │ence     │
    │Service  │  │Service   │  │Service│  │Service  │
    │(8001)   │  │(8002)    │  │(8003) │  │(8004)   │
    │         │  │          │  │       │  │         │
    └─────────┘  └──────────┘  └───────┘  └─────────┘
         │            │            │          │
         │            │            │          │
         └────────────┴────────────┼──────────┘
                                   │
                                   │ HTTP/JSON
                                   │
                    ┌──────────────▼──────────────┐
                    │   SUPABASE (Database)      │
                    │                            │
                    │  Tables:                   │
                    │  • prompts                 │
                    │  • general                 │
                    │  • domain_specific         │
                    │                            │
                    └────────────────────────────┘
```

## Detailed Service Architecture

### 1. API Gateway
**Port**: 8000  
**Purpose**: Orchestrate microservices and expose unified API

```
┌─────────────────────────────────────────┐
│        API Gateway (main.py)            │
├─────────────────────────────────────────┤
│                                         │
│  @app.post("/api/transcribe/")         │
│  ├─ Receive audio file                 │
│  ├─ Normalize MIME type                │
│  ├─ Call Transcription Service         │
│  ├─ Call Prompt Service                │
│  ├─ Call Extraction Service            │
│  ├─ Call Persistence Service           │
│  ├─ Aggregate results                  │
│  └─ Return unified response            │
│                                         │
│  @app.get("/health")                   │
│  └─ Check all services                 │
│                                         │
│  Dependencies:                          │
│  ├─ fastapi, httpx                     │
│  ├─ shared_config.py                   │
│  └─ service_client.py                  │
│                                         │
└─────────────────────────────────────────┘
```

**Request Flow**:
```
1. POST /api/transcribe/ (audio file)
   ↓
2. Normalize MIME type (mp3 → audio/mpeg)
   ↓
3. POST TRANSCRIPTION_SERVICE/transcribe
   ← Returns: transcription, domain, category
   ↓
4. POST PROMPT_SERVICE/validate-and-generate
   ← Returns: is_valid, custom_prompt
   ↓
5. POST EXTRACTION_SERVICE/extract
   ← Returns: domain_specific_data, general_metrics
   ↓
6. POST PERSISTENCE_SERVICE/save
   ← Returns: success, call_id
   ↓
7. Aggregate and return JSON response
```

### 2. Transcription Service
**Port**: 8001  
**Purpose**: Audio transcription and domain/category detection

```
┌─────────────────────────────────────────┐
│   Transcription Service (main.py)       │
├─────────────────────────────────────────┤
│                                         │
│  @app.post("/transcribe")               │
│  ├─ Decode file_bytes from hex         │
│  ├─ Build detection prompt              │
│  ├─ Call Gemini API (Stage 1)           │
│  │  └─ Transcribe + detect domain      │
│  ├─ Parse JSON response                 │
│  ├─ Extract tokens                      │
│  └─ Return result                       │
│                                         │
│  get_domains_categories_text()          │
│  └─ Format known domains for prompt     │
│                                         │
│  Dependencies:                          │
│  ├─ google.generativeai                 │
│  ├─ fastapi                             │
│  └─ shared_config.py                    │
│                                         │
└─────────────────────────────────────────┘
```

**Input/Output**:
```
INPUT:
{
  "file_bytes": "48656c6c6f...", (hex string)
  "mime_type": "audio/mpeg"
}

PROCESSING:
- Decode hex to bytes
- Send to Gemini 2.0-flash with audio
- Gemini returns transcription + domain

OUTPUT:
{
  "transcription": "[00:00-00:05] Customer: Hello...",
  "domain": "healthcare",
  "category": "appointment_scheduling",
  "tokens_stage1": [1250, 890]
}
```

### 3. Prompt Management Service
**Port**: 8002  
**Purpose**: Domain-category validation and prompt generation

```
┌──────────────────────────────────────────────┐
│  Prompt Management Service (main.py)         │
├──────────────────────────────────────────────┤
│                                              │
│  Startup:                                    │
│  ├─ load_domains_from_db()                   │
│  └─ Merge defaults with DB domains           │
│                                              │
│  @app.post("/validate-and-generate")         │
│  ├─ Check is_valid_domain_category()         │
│  ├─ If valid: return None                    │
│  └─ If invalid:                              │
│      ├─ fetch_example_prompts([1,2])        │
│      ├─ generate_custom_prompt() [Gemini]   │
│      ├─ save_prompt_to_db() [ASYNC]         │
│      └─ Return custom_prompt                 │
│                                              │
│  @app.get("/domains")                        │
│  └─ Return VALID_DOMAINS_CATEGORIES          │
│                                              │
│  @app.get("/fetch-prompt")                   │
│  └─ Query Supabase for prompt                │
│                                              │
│  State:                                      │
│  └─ VALID_DOMAINS_CATEGORIES (in-memory)    │
│                                              │
│  Dependencies:                               │
│  ├─ google.generativeai                      │
│  ├─ supabase                                 │
│  ├─ fastapi                                  │
│  └─ shared_config.py                         │
│                                              │
└──────────────────────────────────────────────┘
```

**Key Functions**:
```
is_valid_domain_category(domain, category)
  → bool (True if exists in VALID_DOMAINS_CATEGORIES)

fetch_example_prompts([1, 2])
  → Query Supabase for prompts with id in [1, 2]

generate_custom_prompt(domain, category, examples)
  → Call Gemini with examples to generate prompt

save_prompt_to_db(domain, category, prompt)
  → ASYNC: Insert new domain-category-prompt to DB
```

### 4. Extraction Service
**Port**: 8003  
**Purpose**: Domain-specific data extraction and general call analysis

```
┌──────────────────────────────────────────────┐
│   Extraction Service (main.py)               │
├──────────────────────────────────────────────┤
│                                              │
│  @app.post("/extract")                       │
│  ├─ Get transcription, domain, category      │
│  ├─ Fetch extraction_prompt:                 │
│  │  ├─ Use custom_prompt if provided        │
│  │  ├─ OR fetch_prompt_from_db()             │
│  │  └─ OR use generic fallback               │
│  ├─ Build combined_analysis_prompt:          │
│  │  ├─ PART 1: Domain-specific extraction   │
│  │  └─ PART 2: General call analysis        │
│  ├─ Call Gemini API (Stage 2)                │
│  ├─ Parse JSON response                      │
│  ├─ Extract tokens                           │
│  └─ Return domain_specific + general         │
│                                              │
│  fetch_prompt_from_db(domain, category)      │
│  └─ Query Supabase prompts table             │
│                                              │
│  Dependencies:                               │
│  ├─ google.generativeai                      │
│  ├─ supabase                                 │
│  ├─ fastapi                                  │
│  └─ shared_config.py                         │
│                                              │
└──────────────────────────────────────────────┘
```

**Input/Output**:
```
INPUT:
{
  "transcription": "Full transcript...",
  "domain": "healthcare",
  "category": "appointment_scheduling",
  "custom_prompt": null or "extraction prompt"
}

PROCESSING:
- Build combined analysis prompt (2 parts)
- Send to Gemini 2.0-flash
- Gemini analyzes and returns structured JSON

OUTPUT:
{
  "domain_specific_data": {
    "appointment_date": "2025-12-15",
    "provider": "Dr. Smith",
    ...
  },
  "general_metrics": {
    "section_1_name_extraction": {...},
    "section_2_call_direction_interaction_type": {...},
    "section_3_sentiment_and_intent_detection": {...},
    "section_4_summary_of_conversation_in_brief": "...",
    "section_5_agent_improvement_metrics": {...},
    "section_6_pci_pii_data_detection": [...]
  },
  "tokens_combined": [2100, 1500]
}
```

### 5. Persistence Service
**Port**: 8004  
**Purpose**: Database operations and data storage

```
┌────────────────────────────────────────────┐
│  Persistence Service (main.py)             │
├────────────────────────────────────────────┤
│                                            │
│  @app.post("/save")                        │
│  ├─ Insert to general table                │
│  │  └─ file_name, domain, metrics, tokens  │
│  ├─ Get call_id from response              │
│  ├─ Insert to domain_specific table        │
│  │  ├─ data (JSON string)                  │
│  │  └─ call_id (FK)                        │
│  └─ Return success + IDs                   │
│                                            │
│  @app.get("/call/{call_id}")                │
│  └─ Retrieve call + domain_specific data   │
│                                            │
│  @app.get("/stats")                        │
│  └─ Return table counts                    │
│                                            │
│  Dependencies:                             │
│  ├─ supabase                               │
│  ├─ fastapi                                │
│  └─ shared_config.py                       │
│                                            │
└────────────────────────────────────────────┘
```

**Database Operations**:
```
TABLE: general
┌────────┬──────────┬────────┬──────────┬──────────┬────────┐
│ id (PK)│ file_name│ domain │ category │ sentiment│ tokens │
├────────┼──────────┼────────┼──────────┼──────────┼────────┤
│   42   │ call.mp3 │healthy │ appt     │ Positive │  5740  │
└────────┴──────────┴────────┴──────────┴──────────┴────────┘

TABLE: domain_specific
┌────┬──────────┬───────────────────────┐
│ id │ call_id  │ data (JSON)           │
├────┼──────────┼───────────────────────┤
│156 │ 42 (FK)  │ {...extracted data...}│
└────┴──────────┴───────────────────────┘
```

## 🔄 Complete Request-Response Cycle

### Timeline
```
T+0ms:    Client sends POST /api/transcribe/ with audio.mp3
          ↓
T+50ms:   API Gateway receives file, normalizes MIME
          ↓
T+100ms:  API Gateway → Transcription Service POST /transcribe
          ↓
T+3500ms: Gemini Stage 1 processes (transcription)
          ↓
T+3600ms: Transcription Service returns result
          ↓
T+3700ms: API Gateway → Prompt Service POST /validate-and-generate
          ↓
T+3800ms: Prompt Service checks VALID_DOMAINS_CATEGORIES
          ↓
T+3900ms: Gemini generates custom prompt (if needed)
          ↓
T+4500ms: Prompt Service returns result (± async save)
          ↓
T+4600ms: API Gateway → Extraction Service POST /extract
          ↓
T+4700ms: Extraction Service fetches prompt from DB or uses custom
          ↓
T+6500ms: Gemini Stage 2 processes (extraction)
          ↓
T+6600ms: Extraction Service returns result
          ↓
T+6700ms: API Gateway → Persistence Service POST /save
          ↓
T+7100ms: Persistence Service saves to general table (gets call_id)
          ↓
T+7200ms: Persistence Service saves to domain_specific table
          ↓
T+7500ms: Persistence Service returns success + IDs
          ↓
T+7600ms: API Gateway aggregates all results
          ↓
T+7700ms: API Gateway returns unified JSON response

TOTAL TIME: ~7.7 seconds (varies with API latency)
```

## 🌐 Network Communication

### Docker Network
```
Network Name: audio-hub-network
Type: bridge

Services Connected:
├─ transcription-service (8001)
├─ prompt-service (8002)
├─ extraction-service (8003)
├─ persistence-service (8004)
└─ api-gateway (8000)

Service Discovery:
- Services reach each other by container name
- docker-compose handles DNS resolution
- Example: http://transcription-service:8001/health
```

### HTTP Headers
```
All requests include:
├─ Content-Type: application/json
├─ Timeout: 30 seconds (configurable)
└─ Retry: 3 attempts with exponential backoff

Health Checks:
GET /health
→ {"status": "healthy", "service": "service-name"}
```

## 🔐 Service Boundaries

```
┌─────────────────────────────────────────────────────┐
│         Outside Docker Network (Internet)           │
│                                                     │
│  Clients (Postman, Frontend, Mobile)                │
│  └─ HTTP(S) → http://localhost:8000 or IP:8000     │
└────────────────┬────────────────────────────────────┘
                 │
          Exposed Port 8000 (API Gateway)
                 │
└────────────────▼────────────────────────────────────┐
│        Docker Network (audio-hub-network)           │
│                                                     │
│  API Gateway (8000)                                 │
│  ├─ Internal: http://transcription-service:8001    │
│  ├─ Internal: http://prompt-service:8002           │
│  ├─ Internal: http://extraction-service:8003       │
│  └─ Internal: http://persistence-service:8004      │
│                                                     │
│  Each Service                                       │
│  └─ Only accessible from within network            │
│  └─ Can reach Supabase externally                   │
│                                                     │
└─────────────────────────────────────────────────────┘
                 │
       External API Calls
                 │
          ┌──────▼──────┬──────────────┐
          │   Gemini    │   Supabase   │
          │   API       │   Database   │
          └─────────────┴──────────────┘
```

## 📊 Load Distribution

```
Single Request Flow:
1 Request → API Gateway → 4 Service Calls → 2 Gemini Calls → 2 DB Calls

Multiple Concurrent Requests:
Request 1 ─┐
Request 2 ─┼─→ API Gateway ─→ Services (parallel) ─→ Gemini/DB
Request 3 ─┘

Scaling Opportunity:
- Load balance across multiple API Gateway instances
- Scale individual services based on bottleneck
- Use Kubernetes for orchestration
```

## 🔄 Failure Scenarios

### Service Down
```
If Transcription Service (8001) is down:
1. API Gateway POST → transcription-service fails
2. Retry logic attempts 3 times with backoff
3. After 3 retries, HTTP 500 returned to client

Recovery:
docker-compose restart transcription-service
```

### Database Connection Failure
```
If Supabase is unreachable:
1. Persistence Service can't save
2. Returns success=false
3. API Gateway still returns results to client
4. Data not persisted (can implement queue)

Recovery:
1. Fix Supabase connection
2. Implement message queue for failed saves
3. Retry from queue when connection restored
```

### Gemini API Rate Limit
```
If Gemini API rate limit exceeded:
1. Transcription or Extraction service fails
2. Retry logic applies exponential backoff
3. Eventually HTTP 500 returned

Prevention:
- Monitor token usage
- Implement request queuing
- Add caching layer for prompts
```

## 🎯 Optimization Points

```
CRITICAL PATH:
Transcription (3-5s) → Extraction (2-4s)

OPTIMIZATION:
1. Parallel calls (not possible - dependencies)
2. Cache validation (Prompt Service)
3. Batch database operations
4. Use Gemini API caching

BOTTLENECKS:
- Gemini API latency (50-60% of time)
- Network latency (10-20% of time)
- Database operations (5-10% of time)
```

## 📈 Metrics & Monitoring

```
Key Metrics to Track:
├─ API Gateway
│  ├─ Request latency (P50, P95, P99)
│  ├─ Error rate (5xx, timeouts)
│  └─ Requests per second
│
├─ Service-Level
│  ├─ Service latency
│  ├─ Service health (up/down)
│  └─ Error rates per service
│
├─ External API
│  ├─ Gemini latency
│  ├─ Gemini token usage
│  ├─ Gemini error rate
│  ├─ Supabase latency
│  └─ Supabase connection health
│
└─ Data
   ├─ Total calls processed
   ├─ Calls per domain
   ├─ Average tokens per call
   └─ Database size growth

Alerts:
- Service down (health check fails)
- High latency (>10s)
- High error rate (>5%)
- Database connection failure
- Gemini API quota exceeded
```

---

## Summary

The microservices architecture provides:

✅ **Separation of Concerns**: Each service has single responsibility  
✅ **Independent Deployment**: Services can deploy separately  
✅ **Horizontal Scaling**: Each service scales independently  
✅ **Fault Isolation**: Service failure doesn't crash entire system  
✅ **Technology Flexibility**: Each service can use different tech stack  
✅ **Team Scalability**: Teams can own different services  

**Trade-offs**:
- ⚠️ Increased complexity (distributed system)
- ⚠️ Network latency between services
- ⚠️ Harder local development (need to run multiple services)
- ⚠️ Operational overhead (monitoring, logs, debugging)
