import os
from typing import Optional

from langchain_core.messages import HumanMessage

# Google Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

# OpenAI (also used for Groq via OpenAI-compatible API)
from langchain_openai import ChatOpenAI


# --------------------------------------------------
# Model candidates
# --------------------------------------------------

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]

OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-3.5-turbo",
]

GROK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

GROK_BASE_URL = "https://api.groq.com/openai/v1"


# --------------------------------------------------
# LLM Factory
# --------------------------------------------------

class LLMFactory:
    """
    Centralized LLM access.
    Supports Google Gemini, OpenAI, or Grok (Groq) based on .env config.
    """

    _llm: Optional[object] = None
    _provider: Optional[str] = None
    _model: Optional[str] = None

    @classmethod
    def reset(cls):
        """Reset cached LLM (useful when switching providers)."""
        cls._llm = None
        cls._provider = None
        cls._model = None

    @classmethod
    def get_llm(cls, temperature: float = 0):
        if cls._llm is not None:
            return cls._llm

        provider_pref = os.getenv("LLM_PROVIDER", "auto").lower()

        gemini_key = os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        grok_key = os.getenv("GROK_API_KEY")

        # ------------------------------------------
        # Provider selection
        # ------------------------------------------
        if provider_pref == "gemini" or provider_pref == "google":
            if not gemini_key:
                raise RuntimeError("LLM_PROVIDER=gemini but GEMINI_API_KEY not set")
            return cls._init_gemini(temperature)

        if provider_pref == "openai":
            if not openai_key:
                raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY not set")
            return cls._init_openai(temperature)

        if provider_pref == "grok":
            if not grok_key:
                raise RuntimeError("LLM_PROVIDER=grok but GROK_API_KEY not set")
            return cls._init_grok(temperature)

        if provider_pref == "auto":
            if grok_key:
                return cls._init_grok(temperature)
            if gemini_key:
                return cls._init_gemini(temperature)
            if openai_key:
                return cls._init_openai(temperature)

            raise RuntimeError(
                "No LLM API keys found. "
                "Set GEMINI_API_KEY, OPENAI_API_KEY, or GROK_API_KEY"
            )

        raise RuntimeError(f"Unknown LLM_PROVIDER: {provider_pref}")

    # --------------------------------------------------
    # Google Gemini
    # --------------------------------------------------

    @classmethod
    def _init_gemini(cls, temperature: float):
        last_error = None

        for model in GEMINI_MODELS:
            try:
                llm = ChatGoogleGenerativeAI(
                    model=model,
                    temperature=temperature,
                    google_api_key=os.getenv("GEMINI_API_KEY"),
                )

                llm.invoke([HumanMessage(content="ping")])

                cls._llm = llm
                cls._provider = "gemini"
                cls._model = model

                print(f"[LLM] Using Gemini model: {model}")
                return llm

            except ChatGoogleGenerativeAIError as e:
                print(f"[LLM] Gemini model unavailable: {model}")
                last_error = e

        raise RuntimeError(
            "All Gemini models failed. "
            "Check GEMINI_API_KEY or model availability."
        ) from last_error

    # --------------------------------------------------
    # OpenAI
    # --------------------------------------------------

    @classmethod
    def _init_openai(cls, temperature: float):
        for model in OPENAI_MODELS:
            try:
                llm = ChatOpenAI(
                    model=model,
                    temperature=temperature,
                    api_key=os.getenv("OPENAI_API_KEY"),
                )

                llm.invoke([HumanMessage(content="ping")])

                cls._llm = llm
                cls._provider = "openai"
                cls._model = model

                print(f"[LLM] Using OpenAI model: {model}")
                return llm

            except Exception as e:
                print(f"[LLM] OpenAI model unavailable: {model}")

        raise RuntimeError(
            "All OpenAI models failed. "
            "Check OPENAI_API_KEY or quota."
        )

    # --------------------------------------------------
    # Grok (Groq) — OpenAI-compatible API
    # --------------------------------------------------

    @classmethod
    def _init_grok(cls, temperature: float):
        api_key = os.getenv("GROK_API_KEY")
        last_error = None

        for model in GROK_MODELS:
            try:
                llm = ChatOpenAI(
                    model=model,
                    temperature=temperature,
                    api_key=api_key,
                    base_url=GROK_BASE_URL,
                )

                llm.invoke([HumanMessage(content="ping")])

                cls._llm = llm
                cls._provider = "grok"
                cls._model = model

                print(f"[LLM] Using Grok (Groq) model: {model}")
                return llm

            except Exception as e:
                print(f"[LLM] Grok model unavailable: {model} — {e}")
                last_error = e

        raise RuntimeError(
            "All Grok (Groq) models failed. "
            "Check GROK_API_KEY or model availability."
        ) from last_error

    # --------------------------------------------------
    # Info
    # --------------------------------------------------

    @classmethod
    def info(cls) -> dict:
        return {
            "provider": cls._provider,
            "model": cls._model
        }
