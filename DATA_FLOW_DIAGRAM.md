# Audio Magic Hub - Data Flow Diagram

## 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AUDIO MAGIC HUB SYSTEM                              │
└─────────────────────────────────────────────────────────────────────────────┘

                                   ┌──────────────┐
                                   │   FastAPI    │
                                   │   main.py    │
                                   └──────┬───────┘
                                          │
                ┌─────────────────────────┼─────────────────────────┐
                │                         │                         │
                ▼                         ▼                         ▼
        ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
        │   /health    │         │   /api/      │         │      /       │
        │  Health Check│         │  transcribe/ │         │   Welcome    │
        └──────────────┘         │   MAIN       │         └──────────────┘
                                 │  ENDPOINT    │
                                 └──────┬───────┘
                                        │
                                        │ Audio File
                                        │ (MP3/WAV/M4A)
                                        ▼
```

---

## 🔄 Request Processing Pipeline

### **Complete Data Flow for `/api/transcribe/` Endpoint**

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUEST                                     │
│              (Audio File: MP3, WAV, M4A)                                   │
└────────────────────┬───────────────────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   routes/              │
        │ transcription.py       │
        │  - normalize_mime_type │
        │  - read file bytes     │
        └────────────┬───────────┘
                     │
                     ▼
    ┌────────────────────────────────────────────┐
    │        STAGE 1: TRANSCRIPTION              │
    │  pipelines/transcription_pipeline.py       │
    │                                            │
    │  📍 get_domains_categories_text()          │
    │     ↓ (from domain_service.py)             │
    │     Fetches current domain/category list   │
    │                                            │
    │  📍 generate_content()                     │
    │     ↓ (from gemini_service.py)             │
    │     GEMINI API CALL:                       │
    │     • Transcribes audio with timestamps    │
    │     • Detects domain & category            │
    │     • Returns JSON response                │
    │                                            │
    │  📍 add_discovered_domain_category()       │
    │     ↓ (to domain_service.py)               │
    │     Updates in-memory domain tracking      │
    │                                            │
    │  OUTPUTS:                                  │
    │  ├─ transcription (with timestamps)        │
    │  ├─ domain (e.g., "healthcare")            │
    │  ├─ category (e.g., "appointment_...")     │
    │  └─ tokens_stage1 [input, output]          │
    └────────────────────┬───────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────┐
    │      VALIDATION: PROMPT GENERATION         │
    │    services/prompt_service.py              │
    │                                            │
    │  📍 is_valid_domain_category()             │
    │     ↓ (from domain_service.py)             │
    │     Check if domain/category exists        │
    │                                            │
    │  IF NEW COMBINATION:                       │
    │  ├─ add_discovered_domain_category()       │
    │  ├─ fetch_example_prompts([1,2])           │
    │  │  ↓ (to supabase_service.py)             │
    │  │  Query prompts table by ID              │
    │  │  ↓ SUPABASE: Read example prompts       │
    │  ├─ generate_extraction_prompt()           │
    │  │  ↓ (from gemini_service.py)             │
    │  │  GEMINI API CALL:                       │
    │  │  Uses examples to generate custom       │
    │  │  prompt for new domain-category         │
    │  └─ save_new_prompt_to_db() [ASYNC]        │
    │     ↓ SUPABASE: Insert new prompt          │
    │     Saves generated prompt for future use  │
    │                                            │
    │  IF EXISTING COMBINATION:                  │
    │  └─ Returns None (use DB prompt)           │
    │                                            │
    │  OUTPUTS:                                  │
    │  └─ custom_prompt (or None)                │
    └────────────────────┬───────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────┐
    │     STAGE 2: COMBINED EXTRACTION           │
    │  pipelines/extraction_pipeline.py          │
    │                                            │
    │  📍 fetch_prompt_from_db() [if needed]     │
    │     ↓ (from supabase_service.py)           │
    │     Query prompts table:                   │
    │     WHERE domain=? AND category=?          │
    │     ↓ SUPABASE: Read domain-specific       │
    │        extraction prompt                   │
    │                                            │
    │  📍 generate_content()                     │
    │     ↓ (from gemini_service.py)             │
    │     GEMINI API CALL:                       │
    │     Combined analysis:                     │
    │     • PART 1: Domain-specific extraction   │
    │       (uses specialized prompt)            │
    │     • PART 2: General call analysis        │
    │       - Names (agent, customer)            │
    │       - Metadata (direction, type)         │
    │       - Sentiment & Intent                 │
    │       - Agent Scores (empathy, prof.)      │
    │       - PII Detection                      │
    │                                            │
    │  OUTPUTS:                                  │
    │  ├─ domain_specific_data {}                │
    │  ├─ general_metrics {}                     │
    │  └─ tokens_combined [input, output]        │
    └────────────────────┬───────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────┐
    │       GENERAL METRICS EXTRACTION           │
    │    routes/transcription.py                 │
    │                                            │
    │  📍 extract_general_metrics()              │
    │     Flattens nested sections:              │
    │     ├─ agent_name                          │
    │     ├─ customer_name                       │
    │     ├─ call_direction                      │
    │     ├─ interaction_type                    │
    │     ├─ sentiment                           │
    │     └─ intent                              │
    │                                            │
    │  OUTPUTS:                                  │
    │  └─ extracted_metrics {}                   │
    └────────────────────┬───────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────┐
    │      DATABASE PERSISTENCE LAYER            │
    │    services/supabase_service.py            │
    │                                            │
    │  OPERATION 1: Save General Call Data       │
    │  📍 save_call_to_general_table()           │
    │     ↓ SUPABASE TABLE: "general"            │
    │     INSERT:                                │
    │     ├─ file_name                           │
    │     ├─ domain                              │
    │     ├─ category                            │
    │     ├─ agent_name                          │
    │     ├─ customer_name                       │
    │     ├─ call_direction                      │
    │     ├─ interaction_type                    │
    │     ├─ sentiment                           │
    │     ├─ intent                              │
    │     ├─ tokens_input                        │
    │     ├─ tokens_output                       │
    │     └─ total_tokens                        │
    │     ✅ RETURNS: call_id (PK)               │
    │                                            │
    │  OPERATION 2: Save Domain-Specific Data    │
    │  📍 save_domain_specific_data()            │
    │     ↓ SUPABASE TABLE: "domain_specific"    │
    │     INSERT:                                │
    │     ├─ data (JSON string)                  │
    │     └─ call_id (FK to general.id)          │
    │     ✅ Links to general table               │
    │                                            │
    │  OUTPUTS:                                  │
    │  └─ Database IDs & Status                  │
    └────────────────────┬───────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │    RESPONSE TO CLIENT         │
         │                               │
         │  {                            │
         │    "filename": string,        │
         │    "transcription": string,   │
         │    "domain": string,          │
         │    "category": string,        │
         │    "domain_specific_data": {} │
         │    "general_metrics": {},     │
         │    "token_usage": {           │
         │      "stage1": {...},         │
         │      "stage2": {...},         │
         │      "total": {...}           │
         │    }                          │
         │  }                            │
         └───────────────────────────────┘
```

---

## 📊 Data Structure Flow

### **Stage 1 Output:**
```
stage1_result = {
    "transcription": "[00:00 - 00:15] Customer: Hello...\n[00:15 - 00:30] Agent: Hi...",
    "domain": "healthcare",
    "category": "appointment_scheduling",
    "tokens_stage1": [1250, 890]  # [input, output]
}
```

### **Stage 2 Output:**
```
combined_result = {
    "domain_specific_data": {
        "appointment_date": "2025-12-15",
        "appointment_type": "Consultation",
        "provider_name": "Dr. Smith",
        "insurance_verified": true,
        ...
    },
    "general_metrics": {
        "section_1_name_extraction": {
            "agent_name": "John",
            "customer_name": "Alice"
        },
        "section_2_call_direction_interaction_type": {
            "call_direction": "Inbound",
            "interaction_type": "Conversation"
        },
        "section_3_sentiment_and_intent_detection": {
            "sentiment": "Positive",
            "intent": "Schedule appointment"
        },
        "section_4_summary_of_conversation_in_brief": "Customer called to schedule...",
        "section_5_agent_improvement_metrics": {
            "empathy_score": 8,
            "professionalism_score": 9,
            "knowledge_gap_detection": []
        },
        "section_6_pci_pii_data_detection": ["DOB: 1990-05-10"]
    },
    "tokens_combined": [2100, 1500]
}
```

### **Database Storage:**
```
SUPABASE TABLE: general
┌────────┬──────────┬─────────────┬──────────────┬───────────────┬─────────────┐
│   id   │ file_name│   domain    │   category   │  agent_name   │ sentiment   │
├────────┼──────────┼─────────────┼──────────────┼───────────────┼─────────────┤
│   42   │ call.mp3 │ healthcare  │ appointment_ │    John       │  Positive   │
│        │          │             │  scheduling  │               │             │
└────────┴──────────┴─────────────┴──────────────┴───────────────┴─────────────┘

SUPABASE TABLE: domain_specific
┌────────┬───────────┬────────────────┐
│   id   │  call_id  │      data      │
├────────┼───────────┼────────────────┤
│  156   │    42     │  {...JSON...}  │
└────────┴───────────┴────────────────┘
        └─ Foreign Key to general.id
```

---

## 🔌 External Service Integrations

### **Google Gemini API**
```
REQUEST FLOW:
┌─────────────────┐
│ prompt + audio  │
│ OR prompt only  │
└────────┬────────┘
         │
         ▼
    [GEMINI 2.0-flash]
    • Token counting
    • Content generation
    • JSON parsing
         │
         ▼
┌───────────────────────┐
│ response + tokens     │
│ {text, input, output} │
└───────────────────────┘
```

### **Supabase (PostgreSQL)**
```
OPERATIONS:

1. WRITE (On Startup)
   domain_service.initialize_domains_from_db()
   └─ prompts table: SELECT domain, category
   └─ Merges with default domains

2. READ (During Pipeline)
   prompt_service.fetch_example_prompts()
   └─ prompts table: WHERE id IN [1, 2]
   
   extraction_pipeline.fetch_prompt_from_db()
   └─ prompts table: WHERE domain=? AND category=?

3. WRITE (During Pipeline)
   prompt_service [ASYNC]: save_new_prompt_to_db()
   └─ prompts table: INSERT new domain-category-prompt

4. WRITE (End of Pipeline)
   transcription.py: save_call_to_general_table()
   └─ general table: INSERT call metadata
   
   transcription.py: save_domain_specific_data()
   └─ domain_specific table: INSERT with call_id FK
```

---

## 🗂️ Data Transformation Pipeline

```
LEVEL 1: Raw Input
┌─────────────────────┐
│  Audio File Bytes   │
│  + MIME Type        │
└──────────┬──────────┘

LEVEL 2: Gemini Stage 1 Output
┌──────────────────────────────┐
│  Transcription (with times)   │
│  Domain (string)              │
│  Category (string)            │
│  Token Usage [in, out]         │
└──────────┬───────────────────┘

LEVEL 3: Prompt Validation
┌────────────────────────────────┐
│  ✓ Domain exists in DB         │
│  OR                            │
│  ✗ Generate new prompt (LLM)   │
│    → Save to DB [ASYNC]        │
└──────────┬────────────────────┘

LEVEL 4: Gemini Stage 2 Output
┌──────────────────────────────────┐
│  Domain-Specific Data {}          │
│  General Metrics {} [nested]      │
│  Token Usage [in, out]            │
└──────────┬───────────────────────┘

LEVEL 5: Extracted Metrics
┌────────────────────────────────┐
│  Flattened metrics:            │
│  • agent_name                  │
│  • customer_name               │
│  • sentiment                   │
│  • intent                      │
│  • scores, etc.                │
└──────────┬─────────────────────┘

LEVEL 6: Database Record
┌────────────────────────────────┐
│  general table row:            │
│  • call_id (PK)                │
│  • file_name                   │
│  • domain                       │
│  • category                     │
│  • metrics                      │
│  • tokens                       │
│                                │
│  domain_specific row:          │
│  • call_id (FK)                │
│  • data (JSON)                 │
└────────────────────────────────┘

LEVEL 7: API Response
┌────────────────────────────────┐
│  JSON Response:                │
│  • filename                    │
│  • transcription               │
│  • domain                       │
│  • category                     │
│  • domain_specific_data        │
│  • general_metrics             │
│  • token_usage breakdown       │
└────────────────────────────────┘
```

---

## 🔄 Service Dependencies Map

```
main.py (entry point)
    │
    ├─→ config.py (settings)
    │
    ├─→ services/domain_service.py
    │      ├─→ config.DEFAULT_DOMAINS_CATEGORIES
    │      └─→ services/supabase_service.load_all_domain_categories()
    │
    └─→ routes/transcription.py (@router.post)
           ├─→ utils/constants.MIME_TYPE_MAPPING
           ├─→ pipelines/transcription_pipeline.transcribe_and_detect_domain()
           │      ├─→ services/gemini_service.generate_content()
           │      └─→ services/domain_service (tracking)
           │
           ├─→ services/prompt_service.validate_and_generate_prompt()
           │      ├─→ services/domain_service (validation)
           │      ├─→ services/supabase_service.fetch_example_prompts()
           │      ├─→ services/gemini_service.generate_extraction_prompt()
           │      └─→ services/supabase_service.save_new_prompt_to_db() [ASYNC]
           │
           ├─→ pipelines/extraction_pipeline.extract_all_data()
           │      ├─→ services/supabase_service.fetch_prompt_from_db()
           │      └─→ services/gemini_service.generate_content()
           │
           └─→ services/supabase_service
                  ├─→ save_call_to_general_table()
                  └─→ save_domain_specific_data()
```

---

## ⚙️ Key Processing Decisions

```
┌─────────────────────────────────────────┐
│  DECISION POINT 1: Valid Domain?        │
├─────────────────────────────────────────┤
│  is_valid_domain_category() result      │
│                                         │
│  YES ──→ Use existing DB prompt         │
│  NO  ──→ Generate new prompt (LLM)      │
│          ↓ Save to DB [ASYNC]           │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  DECISION POINT 2: Extraction Prompt    │
├─────────────────────────────────────────┤
│  Priority:                              │
│  1. Custom prompt (from generation)     │
│  2. DB prompt (fetch_prompt_from_db)    │
│  3. Generic fallback prompt             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  DECISION POINT 3: Database Save        │
├─────────────────────────────────────────┤
│  If save_call_to_general_table() OK:    │
│  ├─ Get call_id from response           │
│  ├─ Use call_id for domain_specific FK  │
│  └─ Link both tables successfully       │
│                                         │
│  Else: Skip domain_specific insert      │
└─────────────────────────────────────────┘
```

---

## 📈 Token Usage Tracking

```
STAGE 1: Transcription + Detection
    Input Tokens:  prompt + audio file metadata
    Output Tokens: transcription + JSON response

STAGE 2: Combined Analysis
    Input Tokens:  extraction prompt + transcription
    Output Tokens: domain-specific + general metrics

TOTAL:
    Input Total  = Stage1_in + Stage2_in
    Output Total = Stage1_out + Stage2_out
    Total        = Input Total + Output Total

Efficiency: 30-40% savings vs. 3 separate LLM calls
```

---

## 🚀 Startup Sequence

```
1. main.py starts
   ↓
2. app = FastAPI(...)
   ↓
3. @app.on_event("startup")
   ↓
4. initialize_domains_from_db()
   ├─ VALID_DOMAINS_CATEGORIES = dict(DEFAULT_DOMAINS_CATEGORIES)
   ├─ db_domains = load_all_domain_categories() [Supabase query]
   └─ Merge DB domains with defaults
   ↓
5. App ready at /health, /api/transcribe/, /docs
```

---

## 🔐 Error Handling & Fallbacks

```
GEMINI API FAILURE:
├─ Transcription fails    → HTTP 500 Exception
├─ Prompt generation      → Generic fallback prompt
└─ Extraction fails       → Empty dicts + error message

SUPABASE FAILURES:
├─ Fetch prompt           → Use generic fallback
├─ Save prompt [ASYNC]    → Log error, continue
├─ Save to general        → Skip domain_specific save
└─ Save domain_specific   → Log error, but call recorded

MIME TYPE UNKNOWN:
└─ Attempt normalization  → Fallback to original
```

---

## 📋 Complete Request-Response Cycle

```
REQUEST:
POST /api/transcribe/
Content-Type: multipart/form-data
Body: {file: audio_file.mp3}

PROCESSING TIMELINE:
├─ T+0ms:   Receive file, normalize MIME
├─ T+100ms: Stage 1 - Gemini transcription (~3-5s)
├─ T+5s:    Validate domain-category
├─ T+5.1s:  If new: Generate prompt + save [ASYNC]
├─ T+5.2s:  Stage 2 - Gemini extraction (~2-4s)
├─ T+9s:    Extract & flatten metrics
├─ T+9.1s:  Save to Supabase tables
└─ T+9.2s:  Return response

RESPONSE:
{
  "filename": "call.mp3",
  "transcription": "...",
  "domain": "healthcare",
  "category": "appointment_scheduling",
  "domain_specific_data": {...},
  "general_metrics": {...},
  "token_usage": {
    "stage1_transcription_and_detection": {
      "input": 1250,
      "output": 890,
      "total": 2140
    },
    "stage2_combined_analysis": {
      "input": 2100,
      "output": 1500,
      "total": 3600
    },
    "total": {
      "input": 3350,
      "output": 2390,
      "total": 5740
    }
  }
}

Total Time: ~9-10 seconds
```

---

## 🎯 Summary

**Data Flow Path:**
```
Audio File 
    ↓ (Gemini)
Transcription + Domain Detection
    ↓ (Validation)
Prompt Selection/Generation
    ↓ (Supabase + Gemini)
Domain-Specific + General Analysis
    ↓ (Extraction)
Flattened Metrics
    ↓ (Database)
Supabase: general table + domain_specific table
    ↓ (Response)
Client JSON Response
```

**Key Characteristics:**
- ✅ **2-stage LLM pipeline** for efficiency
- ✅ **Dynamic domain management** with DB persistence
- ✅ **Automatic prompt generation** for new categories
- ✅ **Async background tasks** for non-blocking saves
- ✅ **Comprehensive error handling** with fallbacks
- ✅ **Complete token tracking** across stages
- ✅ **Relational database** linking general ↔ domain_specific
