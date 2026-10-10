import json

import httpx


async def improve_commentary(settings: dict, position: dict) -> str:
    provider = settings.get("ai_provider", "disabled")
    if provider == "disabled":
        return position["coach"]
    base_url = settings.get("ai_base_url", "").rstrip("/")
    if provider == "local" and not base_url:
        base_url = "http://host.docker.internal:11434/v1"
    if not base_url or not settings.get("ai_model"):
        return position["coach"]
    headers = {"Content-Type": "application/json"}
    if settings.get("ai_api_key"):
        headers["Authorization"] = f"Bearer {settings['ai_api_key']}"
    payload = {"model": settings["ai_model"], "temperature": 0.3, "max_tokens": 120,
        "messages": [{"role": "system", "content": "You are a concise chess coach. Never invent engine facts."},
                     {"role": "user", "content": f"Explain {position['san']} ({position['classification']}, loss {position['loss_cp']}cp). Best was {position['best_move_san']}. PV: {' '.join(position['pv'])}"}]}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return position["coach"]
