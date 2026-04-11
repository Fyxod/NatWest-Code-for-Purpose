import asyncio
import itertools
import json
import os
import time
from datetime import datetime, timezone

from google import genai
from langchain_core.output_parsers import PydanticOutputParser
from openai import AsyncOpenAI

from core.config import settings
from core.constants import (
    GEMINI_MODEL,
    LOCAL_LLM_MODEL,
    LOCAL_LLM_PORT,
    OPENAI_MODEL,
    SWITCHES,
)
from core.utils.llm_output_sanitizer import parse_llm_json, sanitize_llm_json

# Directory for logging parse failures
_PARSE_ERRORS_DIR = "DEBUG/parse_errors"
os.makedirs(_PARSE_ERRORS_DIR, exist_ok=True)


def _log_parse_failure(
    source: str,
    attempt: int,
    raw_output: str,
    error: str,
    schema_name: str,
    prompt_snippet: str = "",
):
    """Log a parse failure to a JSONL file for later analysis."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "attempt": attempt,
        "schema": schema_name,
        "error": error,
        "raw_output": raw_output[:5000],
        "prompt_tail": prompt_snippet[-500:] if prompt_snippet else "",
    }
    try:
        log_path = os.path.join(_PARSE_ERRORS_DIR, "failures.jsonl")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Don't let logging failures break the main flow


import core.llm.configurations.local_llm as local_llm_module

# Cache LLM client instances to avoid repeated initialization overhead
_local_llm_cache = {}


def _get_cached_local_llm(model: str, port: int):
    """Return a cached local Ollama client instance, creating one if needed."""
    key = (model, port)
    if key not in _local_llm_cache:
        _local_llm_cache[key] = local_llm_module.MyServerLLM(model=model, port=port)
    return _local_llm_cache[key]


GEMINI_API_KEYS = settings.GEMINI_API_KEYS

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
MAX_RETRIES = 4  # Reduced from 8: JSON sanitizer + json_repair handles most parse errors on first attempt

# Thread-safe API key cycling
_api_key_cycle = itertools.cycle(GEMINI_API_KEYS) if GEMINI_API_KEYS else None
_api_key_lock = asyncio.Lock()


async def _next_api_key():
    """Get the next API key in round-robin fashion, safely under concurrency."""
    async with _api_key_lock:
        if _api_key_cycle is None:
            raise RuntimeError("No API keys configured for GEMINI provider.")
        return next(_api_key_cycle)


def _try_parse(raw_output: str, parser, response_schema):
    """
    Attempt to parse LLM output with sanitization and repair fallbacks.

    Strategy:
    1. Sanitize + PydanticOutputParser.parse() (existing path, now with pre-processing)
    2. parse_llm_json() with json_repair + model_validate (handles malformed JSON)

    Returns parsed structured data or raises on failure.
    """
    cleaned = sanitize_llm_json(raw_output)

    # Strategy 1: Sanitized output through existing parser
    try:
        return parser.parse(cleaned)
    except Exception:
        pass

    # Strategy 2: json_repair + Pydantic model_validate (no LLM call needed)
    return parse_llm_json(raw_output, response_schema)


def _serialize_prompt_messages(messages: list) -> str:
    """
    Convert a list of role/parts message dicts into a readable multi-section
    prompt string.  This preserves the intent of each section (system instructions,
    user question, etc.) rather than dumping a raw Python list repr.
    """
    parts = []
    for msg in messages:
        role = msg.get("role", "system").upper()
        content = msg.get("parts", "")
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


async def invoke_llm(
    response_schema,
    contents,
    remove_thinking=False,
):
    """
    Unified structured LLM invocation with retries and provider routing:
    - LOCAL_LLM
    - GEMINI
    - OPENAI
    Each returns parsed structured data using the same logic.
    """

    # Initialize the parser for structured output
    parser = PydanticOutputParser(pydantic_object=response_schema)

    # Serialize contents properly — multi-turn role/parts dicts become readable
    # prompt sections instead of a raw Python list repr.
    if (
        isinstance(contents, list)
        and contents
        and isinstance(contents[0], dict)
        and "role" in contents[0]
    ):
        serialized = _serialize_prompt_messages(contents)
    else:
        serialized = str(contents)

    # Use different framing for answer-generating schemas vs pure extraction schemas.
    # Answer schemas need the LLM to generate rich content in the "answer" field;
    # "Extract structured data" framing causes short, terse outputs.
    is_answer_schema = (
        hasattr(response_schema, "model_fields")
        and "answer" in response_schema.model_fields
    )

    if is_answer_schema:
        prompt = f"""{serialized}

RESPONSE FORMAT — CRITICAL:
You MUST respond with a single valid JSON object matching this schema:
{parser.get_format_instructions()}

JSON RULES:
1. Output ONLY the JSON object — no markdown fences, no commentary, no text before or after.
2. Escape newlines as \\n and tabs as \\t within JSON string values.
3. If you use internal reasoning (e.g. <think> tags), produce the JSON AFTER the closing tag.
4. The "answer" field should contain your FULL, DETAILED response following the guidelines above. Do NOT truncate or shorten it.
5. For tables inside the answer field, use HTML <table> tags, NOT Markdown pipe tables.
"""
    else:
        prompt = f"""Extract structured data according to this model:
{parser.get_format_instructions()}

Input:
{serialized}

CRITICAL OUTPUT RULES:
1. Output must be valid JSON.
2. Escape newlines as \\n and tabs as \\t within JSON strings.
3. If you generate internal reasoning (e.g. inside <think> tags), you MUST produce the final JSON object AFTER the closing </think> tag.
4. Do not output any text before or after the JSON object.
"""

    # Track the last failed output and parse error for self-correction context
    last_failed_output = None
    last_parse_error = None
    provider_order = []
    if SWITCHES.get("LOCAL_LLM", False):
        provider_order.append("local")
    if SWITCHES.get("GEMINI", False):
        if GEMINI_API_KEYS:
            provider_order.append("gemini")
        else:
            print(
                "GEMINI is enabled, but GEMINI_API_KEYS is empty. Skipping GEMINI provider."
            )
    if SWITCHES.get("OPENAI", False):
        provider_order.append("openai")

    if not provider_order:
        raise RuntimeError(
            "No LLM providers enabled. Set at least one of SWITCHES['LOCAL_LLM'], SWITCHES['GEMINI'], SWITCHES['OPENAI'] to True."
        )

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n=== Attempt {attempt}/{MAX_RETRIES} ===")

        # Build the effective prompt — append correction context if a previous
        # attempt produced output that failed parsing
        effective_prompt = prompt
        if last_failed_output and last_parse_error:
            effective_prompt = (
                f"{prompt}\n\n"
                "--- PREVIOUS ATTEMPT FAILED ---\n"
                "Your previous output could not be parsed. Fix the errors and output valid JSON only.\n\n"
                f"Previous output (rejected):\n{last_failed_output[:2000]}\n\n"
                f"Parse error:\n{last_parse_error}\n\n"
                "Fix the above errors and return ONLY valid JSON matching the schema."
            )
            print(f"[Self-correction] Injecting previous output + error into prompt")

        for provider in provider_order:
            if provider == "local":
                llm_output = None
                try:
                    print(
                        f"Trying LOCAL_LLM model={LOCAL_LLM_MODEL} at port={LOCAL_LLM_PORT}..."
                    )
                    local_llm = _get_cached_local_llm(LOCAL_LLM_MODEL, LOCAL_LLM_PORT)
                    s = time.time()
                    llm_output = await asyncio.to_thread(
                        local_llm._call, effective_prompt
                    )
                    structured = _try_parse(llm_output, parser, response_schema)
                    e = time.time()
                    print(f"Success via LOCAL_LLM, LLM call took {e - s:.2f}s")
                    return structured
                except Exception as e:
                    error_str = str(e)
                    print(f"LOCAL_LLM failed: {error_str}")
                    if llm_output:
                        last_failed_output = llm_output
                        last_parse_error = error_str
                        _log_parse_failure(
                            source="local",
                            attempt=attempt,
                            raw_output=llm_output,
                            error=error_str,
                            schema_name=response_schema.__name__,
                            prompt_snippet=(
                                effective_prompt
                                if isinstance(effective_prompt, str)
                                else str(effective_prompt)
                            ),
                        )
                        print(
                            f"[Self-correction] Captured failed LOCAL_LLM output ({len(llm_output)} chars)"
                        )
                    continue

            if provider == "gemini":
                print("Trying GEMINI...")

                for _ in range(len(GEMINI_API_KEYS)):
                    api_key = await _next_api_key()
                    client = genai.Client(api_key=api_key)
                    s = time.time()
                    raw_output = None
                    try:
                        config = genai.types.GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=200000,
                            response_mime_type="text/plain",
                            safety_settings=[],
                        )

                        if remove_thinking:
                            config.thinking_config = genai.types.ThinkingConfig(
                                thinking_budget=0
                            )

                        response = await asyncio.wait_for(
                            asyncio.to_thread(
                                client.models.generate_content,
                                model=GEMINI_MODEL,
                                contents=effective_prompt,
                                config=config,
                            ),
                            timeout=80,
                        )

                        # Try to extract the raw text content
                        raw_output = None
                        try:
                            raw_output = response.text or str(response)
                        except Exception:
                            raw_output = str(response)

                        structured = _try_parse(raw_output, parser, response_schema)
                        e = time.time()
                        print(f"Success via GEMINI, LLM call took {e - s:.2f}s")
                        return structured

                    except asyncio.TimeoutError:
                        print("GEMINI timeout — switching key...")
                    except Exception as e:
                        print(f"GEMINI error: {e}")
                        if raw_output:
                            last_failed_output = raw_output
                            last_parse_error = str(e)
                            _log_parse_failure(
                                source="gemini",
                                attempt=attempt,
                                raw_output=raw_output,
                                error=str(e),
                                schema_name=response_schema.__name__,
                            )
                        await asyncio.sleep(0.2)
                continue

            if provider == "openai":
                openai_raw = None
                try:
                    print("Trying OPENAI...")
                    s = time.time()
                    response = await openai_client.chat.completions.create(
                        model=OPENAI_MODEL,
                        messages=[{"role": "user", "content": effective_prompt}],
                        temperature=0.2,
                    )

                    openai_raw = response.choices[0].message.content
                    structured = _try_parse(openai_raw, parser, response_schema)
                    e = time.time()
                    print(f"Success via OPENAI, LLM call took {e - s:.2f}s")
                    return structured

                except Exception as e:
                    print(f"OPENAI error: {e}")
                    if openai_raw:
                        last_failed_output = openai_raw
                        last_parse_error = str(e)
                        _log_parse_failure(
                            source="openai",
                            attempt=attempt,
                            raw_output=openai_raw,
                            error=str(e),
                            schema_name=response_schema.__name__,
                        )
                continue

        await asyncio.sleep(2)

    # If all attempts exhausted
    raise RuntimeError(
        f"All {MAX_RETRIES} attempts failed across providers: {' -> '.join(provider_order)}."
    )
