"""
Ollama Cloud API 유틸 — 경량 LLM 호출 (스트리밍 지원)
ministral-3:3b-cloud 모델 사용 (Level 1, 저비용)
"""
from __future__ import annotations
import json
import logging
from typing import AsyncGenerator

import httpx

logger = logging.getLogger("myeonri-api")

# Ollama 서비스 주소 (클러스터 내부)
OLLAMA_BASE = "http://ollama-gpu-service.default.svc.cluster.local:11434"

# 랜딩용 경량 모델 (한국어 자연스러움)
OLLAMA_LIGHT_MODEL = "gpt-oss:20b-cloud"


async def ollama_stream(prompt: str, system: str = "", temperature: float = 0.7) -> AsyncGenerator[str, None]:
    """Ollama Cloud API 스트리밍 호출 → SSE 텍스트 청크 yield"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OLLAMA_LIGHT_MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.3,
            "num_predict": 80,  # 랜딩은 1~2문장이면 충분
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE}/api/chat",
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    logger.warning(f"Ollama API error {resp.status_code}: {error_body.decode()[:200]}")
                    yield f"data: {json.dumps({'error': 'AI 서비스 일시적 오류'})}\n\n"
                    return

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield f"data: {json.dumps({'text': content})}\n\n"
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.warning(f"Ollama API exception: {e}")
        yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"
    finally:
        yield "data: [DONE]\n\n"
