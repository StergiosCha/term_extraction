"""
Lightweight LLM provider utilities for the research app.

Extracted from main.py so research_app.py can run without importing
the heavy main module (which pulls in PyMuPDF, grpc, FAISS, etc.).

Only depends on: aiohttp, google-generativeai, anthropic, openai
All imports are lazy to keep startup fast and memory low.
"""

import os
import asyncio
import logging
from enum import Enum
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


# ── LLM Provider Enum ──────────────────────────────────────────

class LLMProvider(str, Enum):
    # Google Gemini Models
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_0_FLASH_EXP = "gemini-2.0-flash-exp"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_FLASH_8B = "gemini-1.5-flash-8b"

    # Anthropic Claude Models
    CLAUDE_3_7_SONNET = "claude-3-7-sonnet-20250219"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-20241022"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"

    # OpenAI GPT Models
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4 = "gpt-4"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    O1_PREVIEW = "o1-preview"
    O1_MINI = "o1-mini"

    # OpenRouter Models
    OR_CLAUDE_3_7_SONNET = "openrouter/anthropic/claude-3.7-sonnet"
    OR_GPT_4O = "openrouter/openai/gpt-4o"
    OR_DEEPSEEK_V3 = "openrouter/deepseek/deepseek-chat"
    OR_GEMINI_2_0_FLASH_LITE = "openrouter/google/gemini-2.0-flash-lite-001"
    OR_GEMINI_2_5_FLASH_LITE = "openrouter/google/gemini-2.5-flash-lite"
    OR_GEMINI_3_0_FLASH_LITE = "openrouter/google/gemini-3.0-flash-lite"
    OR_GPT_5_2 = "openrouter/openai/gpt-5.2"
    OR_GPT_5_2_PREVIEW = "openrouter/openai/gpt-5.2-preview"
    OR_CLAUDE_4_5_SONNET = "openrouter/anthropic/claude-4.5-sonnet"
    OR_CLAUDE_4_5_OPUS = "openrouter/anthropic/claude-4.5-opus"
    OR_CLAUDE_4_1_SONNET = "openrouter/anthropic/claude-4.1-sonnet"
    OR_CLAUDE_4_1_OPUS = "openrouter/anthropic/claude-4.1-opus"
    OR_LLAMA_3_1_8B = "openrouter/meta-llama/llama-3.1-8b-instruct"
    OR_LLAMA_3_1_70B = "openrouter/meta-llama/llama-3.1-70b-instruct"
    OR_LLAMA_3_1_405B = "openrouter/meta-llama/llama-3.1-405b-instruct"
    OR_MISTRAL_LARGE = "openrouter/mistralai/mistral-large-2411"


# ── Model Configuration ────────────────────────────────────────

MODEL_CONFIG = {
    # Gemini
    LLMProvider.GEMINI_2_5_PRO: {"name": "Gemini 2.5 Pro", "provider": "gemini", "model_id": "gemini-2.0-flash-exp", "description": "Google's latest advanced multimodal model", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.GEMINI_2_0_FLASH_EXP: {"name": "Gemini 2.0 Flash (Experimental)", "provider": "gemini", "model_id": "gemini-2.0-flash-exp", "description": "Fast experimental multimodal model", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.GEMINI_1_5_PRO: {"name": "Gemini 1.5 Pro", "provider": "gemini", "model_id": "gemini-1.5-pro", "description": "Advanced reasoning with long context", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.GEMINI_1_5_FLASH: {"name": "Gemini 1.5 Flash", "provider": "gemini", "model_id": "gemini-1.5-flash", "description": "Fast and efficient model", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.GEMINI_1_5_FLASH_8B: {"name": "Gemini 1.5 Flash 8B", "provider": "gemini", "model_id": "gemini-1.5-flash-8b", "description": "Lightweight 8B parameter model", "max_tokens": 8192, "supports_streaming": True},
    # Claude
    LLMProvider.CLAUDE_3_7_SONNET: {"name": "Claude 3.7 Sonnet", "provider": "anthropic", "model_id": "claude-3-7-sonnet-20250219", "description": "Anthropic's latest advanced reasoning model", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.CLAUDE_3_5_SONNET: {"name": "Claude 3.5 Sonnet", "provider": "anthropic", "model_id": "claude-3-5-sonnet-20241022", "description": "Advanced reasoning and coding", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.CLAUDE_3_5_HAIKU: {"name": "Claude 3.5 Haiku", "provider": "anthropic", "model_id": "claude-3-5-haiku-20241022", "description": "Fast and efficient Claude model", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.CLAUDE_3_OPUS: {"name": "Claude 3 Opus", "provider": "anthropic", "model_id": "claude-3-opus-20240229", "description": "Most capable Claude model", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.CLAUDE_3_SONNET: {"name": "Claude 3 Sonnet", "provider": "anthropic", "model_id": "claude-3-sonnet-20240229", "description": "Balanced performance and speed", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.CLAUDE_3_HAIKU: {"name": "Claude 3 Haiku", "provider": "anthropic", "model_id": "claude-3-haiku-20240307", "description": "Fastest Claude model", "max_tokens": 4096, "supports_streaming": True},
    # OpenAI
    LLMProvider.GPT_4O: {"name": "GPT-4o", "provider": "openai", "model_id": "gpt-4o", "description": "OpenAI's latest multimodal model", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.GPT_4O_MINI: {"name": "GPT-4o Mini", "provider": "openai", "model_id": "gpt-4o-mini", "description": "Faster and cheaper GPT-4o variant", "max_tokens": 16384, "supports_streaming": True},
    LLMProvider.GPT_4_TURBO: {"name": "GPT-4 Turbo", "provider": "openai", "model_id": "gpt-4-turbo", "description": "Enhanced GPT-4 with longer context", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.GPT_4: {"name": "GPT-4", "provider": "openai", "model_id": "gpt-4", "description": "Original GPT-4 model", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.GPT_3_5_TURBO: {"name": "GPT-3.5 Turbo", "provider": "openai", "model_id": "gpt-3.5-turbo", "description": "Fast and cost-effective model", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.O1_PREVIEW: {"name": "O1 Preview", "provider": "openai", "model_id": "o1-preview", "description": "OpenAI's reasoning model", "max_tokens": 4096, "supports_streaming": False},
    LLMProvider.O1_MINI: {"name": "O1 Mini", "provider": "openai", "model_id": "o1-mini", "description": "Smaller reasoning model", "max_tokens": 4096, "supports_streaming": False},
    # OpenRouter
    LLMProvider.OR_CLAUDE_3_7_SONNET: {"name": "Claude 3.7 Sonnet (OR)", "provider": "openrouter", "model_id": "anthropic/claude-3.7-sonnet", "description": "Claude 3.7 via OpenRouter", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.OR_GPT_4O: {"name": "GPT-4o (OR)", "provider": "openrouter", "model_id": "openai/gpt-4o", "description": "GPT-4o via OpenRouter", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.OR_DEEPSEEK_V3: {"name": "DeepSeek V3 (OR)", "provider": "openrouter", "model_id": "deepseek/deepseek-chat", "description": "DeepSeek V3 via OpenRouter", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.OR_GEMINI_2_0_FLASH_LITE: {"name": "Gemini 2.0 Flash Lite (OR)", "provider": "openrouter", "model_id": "google/gemini-2.0-flash-lite-001", "description": "Fast lightweight Gemini 2.0", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.OR_GEMINI_2_5_FLASH_LITE: {"name": "Gemini 2.5 Flash Lite (OR)", "provider": "openrouter", "model_id": "google/gemini-2.5-flash-lite", "description": "Upcoming fast Gemini 2.5", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.OR_GEMINI_3_0_FLASH_LITE: {"name": "Gemini 3.0 Flash Lite (OR)", "provider": "openrouter", "model_id": "google/gemini-3.0-flash-lite", "description": "Upcoming modular Gemini 3.0", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.OR_GPT_5_2: {"name": "GPT-5.2 (OR)", "provider": "openrouter", "model_id": "openai/gpt-5.2", "description": "Next generation GPT", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.OR_GPT_5_2_PREVIEW: {"name": "GPT-5.2 Preview (OR)", "provider": "openrouter", "model_id": "openai/gpt-5.2-preview", "description": "Next generation GPT early preview", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.OR_CLAUDE_4_5_SONNET: {"name": "Claude 4.5 Sonnet (OR)", "provider": "openrouter", "model_id": "anthropic/claude-4.5-sonnet", "description": "Next generation Claude Sonnet", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.OR_CLAUDE_4_5_OPUS: {"name": "Claude 4.5 Opus (OR)", "provider": "openrouter", "model_id": "anthropic/claude-4.5-opus", "description": "Next generation Claude Opus", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.OR_CLAUDE_4_1_SONNET: {"name": "Claude 4.1 Sonnet (OR)", "provider": "openrouter", "model_id": "anthropic/claude-4.1-sonnet", "description": "Upcoming Claude 4.1 Series", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.OR_CLAUDE_4_1_OPUS: {"name": "Claude 4.1 Opus (OR)", "provider": "openrouter", "model_id": "anthropic/claude-4.1-opus", "description": "Upcoming Claude 4.1 Opus", "max_tokens": 4096, "supports_streaming": True},
    LLMProvider.OR_LLAMA_3_1_8B: {"name": "Llama 3.1 8B (OR)", "provider": "openrouter", "model_id": "meta-llama/llama-3.1-8b-instruct", "description": "Fast Meta Llama 3.1", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.OR_LLAMA_3_1_70B: {"name": "Llama 3.1 70B (OR)", "provider": "openrouter", "model_id": "meta-llama/llama-3.1-70b-instruct", "description": "Powerful Meta Llama 3.1", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.OR_LLAMA_3_1_405B: {"name": "Llama 3.1 405B (OR)", "provider": "openrouter", "model_id": "meta-llama/llama-3.1-405b-instruct", "description": "Massive Meta Llama 3.1", "max_tokens": 8192, "supports_streaming": True},
    LLMProvider.OR_MISTRAL_LARGE: {"name": "Mistral Large (OR)", "provider": "openrouter", "model_id": "mistralai/mistral-large-2411", "description": "Mistral's flagship large model", "max_tokens": 8192, "supports_streaming": True},
}


# ── MultiLLMManager ────────────────────────────────────────────

class MultiLLMManager:
    """Manages multiple LLM providers with support for user API keys."""

    def __init__(self):
        self.default_provider = LLMProvider.GEMINI_2_5_PRO
        self.user_api_keys = {}  # {session_id: {provider_type: api_key}}
        self.system_api_keys = {
            "gemini": self._get_system_api_key("GEMINI_API_KEY", ".gemini_api_key"),
            "anthropic": self._get_system_api_key("ANTHROPIC_API_KEY", ".anthropic_api_key"),
            "openai": self._get_system_api_key("OPENAI_API_KEY", ".openai_api_key"),
            "openrouter": self._get_system_api_key("OPENROUTER_API_KEY", ".openrouter_api_key"),
        }

    def _get_system_api_key(self, env_var: str, file_path: str) -> Optional[str]:
        api_key = os.environ.get(env_var)
        if api_key:
            return api_key
        try:
            with open(file_path, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return None

    def set_user_api_key(self, session_id: str, provider_type: str, api_key: str):
        if session_id not in self.user_api_keys:
            self.user_api_keys[session_id] = {}
        self.user_api_keys[session_id][provider_type] = api_key
        logger.info(f"Set user API key for {provider_type} (session: {session_id[:8]}...)")

    def get_api_key(self, session_id: Optional[str], provider_type: str) -> Optional[str]:
        if session_id and session_id in self.user_api_keys:
            user_key = self.user_api_keys[session_id].get(provider_type)
            if user_key:
                return user_key
        return self.system_api_keys.get(provider_type)

    def get_available_models(self, session_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        available = {}
        for model_enum, config in MODEL_CONFIG.items():
            provider_type = config["provider"]
            if provider_type != "openrouter":
                continue
            api_key = self.get_api_key(session_id, provider_type)
            available[model_enum.value] = {
                "name": config["name"],
                "description": config["description"],
                "provider": provider_type,
                "model_id": config["model_id"],
                "available": api_key is not None,
                "has_user_key": session_id and session_id in self.user_api_keys and provider_type in self.user_api_keys.get(session_id, {}),
                "max_tokens": config["max_tokens"],
                "supports_streaming": config["supports_streaming"],
            }
        return available

    def is_model_available(self, model: str, session_id: Optional[str] = None) -> bool:
        try:
            model_enum = LLMProvider(model)
            config = MODEL_CONFIG[model_enum]
            provider_type = config["provider"]
            api_key = self.get_api_key(session_id, provider_type)
            return api_key is not None
        except (ValueError, KeyError):
            return False

    async def generate_with_provider(self, prompt: str, provider: str, timeout: int = 30, session_id: Optional[str] = None) -> str:
        try:
            model_enum = LLMProvider(provider)
        except ValueError:
            raise ValueError(f"Unknown model: '{provider}'")

        config = MODEL_CONFIG.get(model_enum)
        if not config:
            raise ValueError(f"Model configuration not found: '{provider}'")

        provider_type = config["provider"]
        model_id = config["model_id"]
        api_key = self.get_api_key(session_id, provider_type)

        if not api_key:
            raise RuntimeError(f"API key not found for {provider_type}. Please set your API key.")

        try:
            if provider_type == "gemini":
                return await self._generate_gemini(prompt, api_key, model_id, timeout)
            elif provider_type == "anthropic":
                return await self._generate_claude(prompt, api_key, model_id, timeout, config["max_tokens"])
            elif provider_type == "openai":
                return await self._generate_openai(prompt, api_key, model_id, timeout, config["max_tokens"])
            elif provider_type == "openrouter":
                return await self._generate_openrouter(prompt, api_key, model_id, timeout, config["max_tokens"])
            else:
                raise ValueError(f"Unknown provider type: {provider_type}")
        except asyncio.TimeoutError:
            logger.error(f"LLM generation timed out after {timeout}s with {provider}")
            raise TimeoutError(f"Request timed out after {timeout}s. Try a shorter text or different model.")

    async def _generate_gemini(self, prompt: str, api_key: str, model_id: str, timeout: int) -> str:
        import google.generativeai as genai
        loop = asyncio.get_event_loop()

        def call_gemini():
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_id)
            response = model.generate_content(prompt)
            return response.text

        return await asyncio.wait_for(loop.run_in_executor(None, call_gemini), timeout=timeout)

    async def _generate_claude(self, prompt: str, api_key: str, model_id: str, timeout: int, max_tokens: int) -> str:
        import anthropic
        loop = asyncio.get_event_loop()

        def call_claude():
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

        return await asyncio.wait_for(loop.run_in_executor(None, call_claude), timeout=timeout)

    async def _generate_openai(self, prompt: str, api_key: str, model_id: str, timeout: int, max_tokens: int) -> str:
        import openai
        loop = asyncio.get_event_loop()

        def call_openai():
            client = openai.OpenAI(api_key=api_key)
            if model_id.startswith("o1"):
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                )
            else:
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_completion_tokens=max_tokens,
                    temperature=1,
                )
            return response.choices[0].message.content

        return await asyncio.wait_for(loop.run_in_executor(None, call_openai), timeout=timeout)

    async def _generate_openrouter(self, prompt: str, api_key: str, model_id: str, timeout: int, max_tokens: int) -> str:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://textcraft.ai",
                    "X-Title": "TextCraft AI",
                },
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error_text = await response.text()
                    logger.error(f"OpenRouter error: {response.status} - {error_text}")
                    raise RuntimeError(f"OpenRouter failed ({response.status}): {error_text}")


# ── Singleton + convenience function ───────────────────────────

llm_manager = MultiLLMManager()


async def generate_with_timeout_multi(prompt: str, provider: str = None, timeout: int = 30, session_id: Optional[str] = None) -> str:
    """Generate with timeout using specified provider."""
    if provider is None:
        provider = llm_manager.default_provider.value
    return await llm_manager.generate_with_provider(prompt, provider, timeout, session_id)


# ── Lightweight document text extraction ───────────────────────
# Replaces EletoDocumentScraper for PDF/DOCX, using only PyPDF2
# and python-docx (both already in requirements.txt).

def extract_text_from_pdf(content_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyPDF2."""
    import PyPDF2
    from io import BytesIO
    reader = PyPDF2.PdfReader(BytesIO(content_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def extract_text_from_docx(content_bytes: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    import docx
    from io import BytesIO
    doc = docx.Document(BytesIO(content_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)
