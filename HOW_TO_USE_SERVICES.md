# How to Use Microservices

This guide explains how to use any microservice in the audio_magicHub system, with detailed examples for the **Transcription Service**.

---

## Quick Start

### 1. Start the Service

**Option A: Direct Python (Development)**
```bash
cd microservices/transcription_service
python main.py
```

**Option B: Docker Compose (Recommended)**
```bash
docker-compose up -d transcription-service
```

**Option C: Docker Individual Service**
```bash
docker build -t transcription-service microservices/transcription_service/
docker run -p 8001:8001 transcription-service
```

The service will start and listen on its configured port.

---

## Service Endpoints

### Health Check
Every service has a `/health` endpoint to verify it's running:

```bash
curl http://localhost:8001/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "transcription-service"
}
```

---

## Using Transcription Service

### Endpoint
```
POST http://localhost:8001/transcribe
```

### Request Format

The endpoint accepts JSON with audio file data:

```json
{
  "file_bytes": "hex_encoded_audio_data",
  "mime_type": "audio/mpeg"
}
```

**Parameters:**
- `file_bytes` (string, required): Audio file contents as hexadecimal string
- `mime_type` (string, optional): MIME type of audio file (default: "audio/mpeg")

### Response Format

```json
{
  "transcription": "[00:00 - 00:05] Agent: Hello, how can I help?\n[00:05 - 00:10] Customer: I need to schedule an appointment",
  "domain": "healthcare",
  "category": "appointment_scheduling",
  "tokens_stage1": [1250, 890]
}
```

**Response Fields:**
- `transcription`: Full text with timestamps and speaker labels
- `domain`: Business domain (e.g., "healthcare", "finance", "ecommerce")
- `category`: Specific category within domain (e.g., "appointment_scheduling")
- `tokens_stage1`: [input_tokens, output_tokens] used by Gemini API

---

## Usage Examples

### Example 1: Using cURL (Command Line)

**Step 1: Convert audio file to hex**

On **Windows PowerShell**:
```powershell
$audioFile = "C:\path\to\audio.mp3"
$bytes = [System.IO.File]::ReadAllBytes($audioFile)
$hex = [System.BitConverter]::ToString($bytes) -replace "-", ""
$hex | Out-File "audio_hex.txt"
```

On **Linux/Mac**:
```bash
xxd -p -c 256 audio.mp3 | tr -d '\n' > audio_hex.txt
```

**Step 2: Send to service**
```bash
$hex = Get-Content "audio_hex.txt"
$body = @{
    file_bytes = $hex
    mime_type = "audio/mpeg"
} | ConvertTo-Json

curl -X POST "http://localhost:8001/transcribe" `
  -H "Content-Type: application/json" `
  -d $body
```

### Example 2: Using Python

```python
import requests
import json

# Load audio file
with open("audio.mp3", "rb") as f:
    audio_bytes = f.read()

# Convert to hex
file_hex = audio_bytes.hex()

# Prepare request
url = "http://localhost:8001/transcribe"
payload = {
    "file_bytes": file_hex,
    "mime_type": "audio/mpeg"
}

# Send request
response = requests.post(url, json=payload)
result = response.json()

# Print results
print("Transcription:")
print(result["transcription"])
print(f"\nDomain: {result['domain']}")
print(f"Category: {result['category']}")
print(f"Tokens used: {result['tokens_stage1']}")
```

### Example 3: Using FastAPI TestClient

```python
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add service path
sys.path.insert(0, "microservices/transcription_service")
from main import app

client = TestClient(app)

# Load and convert audio
with open("audio.mp3", "rb") as f:
    file_hex = f.read().hex()

# Test endpoint
response = client.post("/transcribe", json={
    "file_bytes": file_hex,
    "mime_type": "audio/mpeg"
})

assert response.status_code == 200
print(response.json())
```

### Example 4: Using Postman

1. **Create new request**
   - Method: `POST`
   - URL: `http://localhost:8001/transcribe`

2. **Headers tab**
   ```
   Content-Type: application/json
   ```

3. **Body tab** (select "raw" → "JSON")
   ```json
   {
     "file_bytes": "48656c6c6f20776f726c64...",
     "mime_type": "audio/mpeg"
   }
   ```

4. **Send** and view response

---

## Common MIME Types

| File Format | MIME Type |
|-------------|-----------|
| MP3 | `audio/mpeg` |
| WAV | `audio/wav` |
| OGG | `audio/ogg` |
| FLAC | `audio/flac` |
| M4A | `audio/mp4` or `audio/x-m4a` |
| WebM | `audio/webm` |

---

## Error Handling

### Common Errors

**1. Service Not Running**
```bash
curl http://localhost:8001/health
# Connection refused
```
**Solution**: Start the service with `python main.py`

**2. Invalid File Format**
```json
{
  "detail": "Transcription failed: Invalid audio format"
}
```
**Solution**: Ensure audio file is valid and MIME type matches format

**3. Invalid Hex String**
```json
{
  "detail": "Transcription failed: Invalid hex string"
}
```
**Solution**: Ensure `file_bytes` is properly encoded as hexadecimal

**4. Gemini API Error**
```json
{
  "detail": "Transcription failed: API key invalid or quota exceeded"
}
```
**Solution**: Check `GEMINI_API_KEY` in `.env` file

---

## Testing the Service

### Unit Test Example

```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    from microservices.transcription_service.main import app
    return TestClient(app)

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_transcription_with_sample_audio(client):
    # Load sample audio file
    with open("sample_audio.mp3", "rb") as f:
        file_hex = f.read().hex()
    
    response = client.post("/transcribe", json={
        "file_bytes": file_hex,
        "mime_type": "audio/mpeg"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "transcription" in data
    assert "domain" in data
    assert "category" in data
    assert "tokens_stage1" in data
    assert isinstance(data["tokens_stage1"], list)
    assert len(data["tokens_stage1"]) == 2
```

**Run tests:**
```bash
pytest tests/test_transcription_service.py -v
```

---

## Using via API Gateway

You don't typically call Transcription Service directly in production. Instead, use the **API Gateway** which orchestrates all services:

```bash
curl -X POST "http://localhost:8000/api/transcribe/" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@audio.mp3"
```

The API Gateway will:
1. Call Transcription Service
2. Call Prompt Management Service
3. Call Extraction Service
4. Call Persistence Service
5. Return unified response

---

## Configuration

### Environment Variables

Create `.env` file in project root:

```env
# Transcription Service
TRANSCRIPTION_SERVICE_PORT=8001

# Gemini API
GEMINI_API_KEY=your_api_key_here
LLM_MODEL=gemini-2.0-flash

# Supabase (for other services)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_key_here
```

### Service Port Configuration

Modify in `shared_config.py`:

```python
TRANSCRIPTION_SERVICE_PORT = 8001  # Change port here
TRANSCRIPTION_SERVICE_URL = "http://transcription-service:8001"
```

---

## Performance Tips

1. **Use Docker Compose** for best performance
   - Services run in isolated containers
   - Automatic network resolution
   - Proper resource allocation

2. **Monitor Token Usage**
   - API returns `tokens_stage1: [input, output]`
   - Track cumulative usage to manage costs
   - Consider caching for repeated prompts

3. **Parallel Processing**
   - If sending multiple files, batch them
   - Use async clients for concurrent requests
   - Load balance across service instances

4. **Audio File Optimization**
   - Compress audio files before processing
   - Use appropriate sample rate (16kHz is often sufficient)
   - Keep file size under 25MB (Gemini limit)

---

## Debugging

### View Service Logs

**Docker Compose:**
```bash
docker-compose logs -f transcription-service
```

**Direct Python:**
```bash
python microservices/transcription_service/main.py
# Logs appear in console
```

### Enable Debug Mode

In service's `main.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test Endpoint Directly

```bash
# Check service is running
curl http://localhost:8001/health -v

# View API documentation (FastAPI Swagger)
curl http://localhost:8001/docs
# Open http://localhost:8001/docs in browser
```

---

## Complete Workflow

### Step-by-Step Example

```python
import requests
import json
from pathlib import Path

def transcribe_audio(audio_file_path: str) -> dict:
    """
    Complete workflow to transcribe audio file
    """
    
    # Step 1: Load audio file
    print(f"📁 Loading {audio_file_path}...")
    with open(audio_file_path, "rb") as f:
        audio_bytes = f.read()
    
    # Step 2: Convert to hex
    print("🔄 Converting to hex...")
    file_hex = audio_bytes.hex()
    
    # Step 3: Prepare request
    print("📋 Preparing request...")
    url = "http://localhost:8001/transcribe"
    payload = {
        "file_bytes": file_hex,
        "mime_type": "audio/mpeg"
    }
    
    # Step 4: Send request
    print("🚀 Sending to Transcription Service...")
    response = requests.post(url, json=payload)
    
    # Step 5: Handle response
    if response.status_code == 200:
        result = response.json()
        print("✅ Success!")
        print(f"\n📝 Transcription:\n{result['transcription']}\n")
        print(f"🏷️  Domain: {result['domain']}")
        print(f"📌 Category: {result['category']}")
        print(f"💰 Tokens: Input={result['tokens_stage1'][0]}, Output={result['tokens_stage1'][1]}")
        return result
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return None

# Usage
if __name__ == "__main__":
    result = transcribe_audio("path/to/audio.mp3")
```

---

## Next Steps

After getting transcription results, you can:

1. **Validate with Prompt Service**
   ```bash
   POST /validate-and-generate
   ```

2. **Extract data with Extraction Service**
   ```bash
   POST /extract
   ```

3. **Save with Persistence Service**
   ```bash
   POST /save
   ```

Or use the **API Gateway** to do all of this automatically!

```bash
POST /api/transcribe/
```

---

## Support

For issues or questions:
- Check service logs: `docker-compose logs service-name`
- View API docs: `http://localhost:8001/docs`
- Read MICROSERVICES_README.md for architecture details
- Check MICROSERVICES_ARCHITECTURE.md for system diagrams
