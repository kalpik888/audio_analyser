"""
Shared utilities for inter-service communication
"""
import httpx
import asyncio
from typing import Dict, Any
from shared_config import SERVICE_TIMEOUT

class ServiceClient:
    """
    HTTP client for inter-service communication with retry logic
    """
    
    def __init__(self, service_url: str, timeout: int = SERVICE_TIMEOUT):
        self.service_url = service_url
        self.timeout = timeout
        self.max_retries = 3
    
    async def post(self, endpoint: str, data: Dict[str, Any], retry: int = 0) -> Dict[str, Any]:
        """
        POST request with retry logic
        """
        url = f"{self.service_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=data)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            if retry < self.max_retries:
                print(f"⚠️  Retry {retry + 1}/{self.max_retries} for {url}")
                await asyncio.sleep(2 ** retry)  # Exponential backoff
                return await self.post(endpoint, data, retry + 1)
            else:
                print(f"❌ Service call failed after {self.max_retries} retries: {url}")
                raise
    
    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        GET request with retry logic
        """
        url = f"{self.service_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"❌ GET request failed: {url} - {e}")
            raise


async def call_transcription_service(file_bytes: bytes, mime_type: str) -> Dict[str, Any]:
    """Call Transcription Service"""
    from shared_config import TRANSCRIPTION_SERVICE_URL
    client = ServiceClient(TRANSCRIPTION_SERVICE_URL)
    return await client.post("/transcribe", {
        "file_bytes": file_bytes.hex(),
        "mime_type": mime_type
    })


async def call_prompt_service(domain: str, category: str, example_ids: list = None) -> Dict[str, Any]:
    """Call Prompt Management Service"""
    from shared_config import PROMPT_SERVICE_URL
    client = ServiceClient(PROMPT_SERVICE_URL)
    return await client.post("/validate-and-generate", {
        "domain": domain,
        "category": category,
        "example_ids": example_ids or [1, 2]
    })


async def call_extraction_service(transcription: str, domain: str, category: str, custom_prompt: str = None) -> Dict[str, Any]:
    """Call Extraction Service"""
    from shared_config import EXTRACTION_SERVICE_URL
    client = ServiceClient(EXTRACTION_SERVICE_URL)
    return await client.post("/extract", {
        "transcription": transcription,
        "domain": domain,
        "category": category,
        "custom_prompt": custom_prompt
    })


async def call_persistence_service(general_data: Dict[str, Any], domain_specific_data: str) -> Dict[str, Any]:
    """Call Persistence Service"""
    from shared_config import PERSISTENCE_SERVICE_URL
    client = ServiceClient(PERSISTENCE_SERVICE_URL)
    return await client.post("/save", {
        "general_data": general_data,
        "domain_specific_data": domain_specific_data
    })
