"""
Unified LLM Client and Invocation Bridge.

Provides a single-source-of-truth OpenAI-compatible client singleton and stateless
functions for synchronous text and structured JSON completions across all pipelines.
Zero OOP classes; pure functional interfaces.
"""

import json
import re
from typing import Any, Dict, List, Optional
from openai import OpenAI
from config import get_llm_settings

# Module-level client cache
_CLIENT_INSTANCE: Optional[OpenAI] = None


def get_openai_client(force_reload: bool = False) -> OpenAI:
    """
    Returns a cached OpenAI client singleton configured from environment settings.
    If force_reload is True, re-instantiates the client.
    """
    global _CLIENT_INSTANCE
    if _CLIENT_INSTANCE is None or force_reload:
        cfg = get_llm_settings()
        _CLIENT_INSTANCE = OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
        )
    return _CLIENT_INSTANCE


def extract_json_payload(raw_text: str) -> Any:
    """
    Robustly extracts and parses JSON from raw LLM output, stripping markdown fences
    and finding json structures if wrapped in conversational text.
    """
    cleaned = raw_text.strip()
    
    # Strip markdown code blocks like ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: Find first '{' and last '}'
    brace_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: Find first '[' and last ']'
    bracket_match = re.search(r"(\[.*\])", cleaned, re.DOTALL)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(1))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse valid JSON from LLM output:\n{raw_text[:300]}")


def call_llm(
    prompt: Optional[str] = None,
    system_prompt: str = "",
    json_mode: bool = False,
    temperature: float = 0.0,
    model_override: Optional[str] = None,
    user_prompt: Optional[str] = None,
) -> str:
    """
    Executes a chat completion call against the configured LLM API.
    Returns the stripped string content of the response.
    Supports either `prompt` or `user_prompt` keyword arguments for maximum compatibility.
    """
    effective_prompt = prompt if prompt is not None else (user_prompt or "")
    client = get_openai_client()
    cfg = get_llm_settings()
    model = model_override or cfg["model"]

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": effective_prompt})

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    return content.strip()


def call_llm_json(
    prompt: Optional[str] = None,
    system_prompt: str = "",
    temperature: float = 0.0,
    model_override: Optional[str] = None,
    user_prompt: Optional[str] = None,
) -> Any:
    """
    Invokes the LLM in JSON mode and returns the parsed Python dictionary or list.
    Handles fence stripping and malformed json edge cases.
    Supports either `prompt` or `user_prompt` keyword arguments.
    """
    effective_prompt = prompt if prompt is not None else (user_prompt or "")
    raw_response = call_llm(
        prompt=effective_prompt,
        system_prompt=system_prompt,
        json_mode=True,
        temperature=temperature,
        model_override=model_override,
    )
    return extract_json_payload(raw_response)

