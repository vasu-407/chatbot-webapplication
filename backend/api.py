# app.py
import os
import requests

# Default OpenRouter model (free-tier friendly)
DEFAULT_MODEL = "openai/gpt-3.5-turbo"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY not set in environment")

def chat_response(message: str, session_id=None, model_name: str = None) -> dict:
    """
    This function is dynamically loaded by server.py
    Signature is IMPORTANT — do not change parameter names
    """

    model = model_name or DEFAULT_MODEL

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "HealSphere Chatbot"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful AI assistant that responds clearly and concisely."
            },
            {
                "role": "user",
                "content": message
            }
        ],
        "max_tokens": 300
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()

    reply = data["choices"][0]["message"]["content"]

    return {
        "reply": reply,
        "model": model,
        "metadata": {
            "provider": "openrouter",
            "usage": data.get("usage", {})
        },
        "sources": []
    }
