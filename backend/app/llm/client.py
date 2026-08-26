import os

from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def get_chat_model():
    provider = os.getenv("LLM_PROVIDER", "openai").strip()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
    if not provider or not model:
        raise ValueError("LLM_PROVIDER and LLM_MODEL must be set")
    return init_chat_model(f"{provider}:{model}")


def provider_api_key_present() -> bool:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    key_by_provider = {
        "groq": "GROQ_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google_genai": "GOOGLE_API_KEY",
        "google": "GOOGLE_API_KEY",
        "ollama": None,
    }
    env_name = key_by_provider.get(provider, "OPENAI_API_KEY")
    if env_name is None:
        return True
    return bool(os.getenv(env_name, "").strip())
