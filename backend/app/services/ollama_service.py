import httpx
from fastapi import HTTPException
from app.core.config import settings

async def ask_ollama(messages: list[dict[str, str]]) -> str:
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json={"model": settings.ollama_model, "messages": messages, "stream": False})
            response.raise_for_status()
            answer = response.json().get("message", {}).get("content")
            if not answer:
                raise HTTPException(502, "Ollama returned an empty response")
            return answer
    except httpx.TimeoutException:
        raise HTTPException(504, "Ollama request timed out")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"Ollama returned HTTP {exc.response.status_code}")
    except httpx.RequestError:
        raise HTTPException(503, "Cannot connect to Ollama; check that it is running")


async def stream_ollama(messages: list[dict[str, str]]):
    """Yield generated text fragments from Ollama NDJSON."""
    import json
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=None, write=30, pool=10)) as client:
        async with client.stream(
            "POST", f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={"model": settings.ollama_model, "messages": messages,
                  "stream": True, "keep_alive": "30m"},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                item = json.loads(line)
                if item.get("error"):
                    raise RuntimeError(item["error"])
                content = item.get("message", {}).get("content", "")
                if content:
                    yield content
