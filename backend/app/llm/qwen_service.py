"""
llm/qwen_service.py — Ollama HTTP integration for Qwen3 + HF Fallback.

Primary: Ollama HTTP API (http://localhost:11434/api/generate) with qwen3:8b
Fallback: HuggingFace Transformers Pipeline (kept for local execution)
"""

from __future__ import annotations
import json
import threading
from typing import Optional, Generator

import requests
from loguru import logger

from app.core.config import get_settings

settings = get_settings()

# ── HF Fallback globals ───────────────────────────────────────────────────────
_lock = threading.Lock()
_hf_pipeline = None
_hf_loaded = False


def _load_hf_pipeline():
    """Load the HuggingFace fallback model."""
    global _hf_pipeline, _hf_loaded
    with _lock:
        if _hf_loaded or not settings.llm_fallback_enabled:
            return
        try:
            from transformers import pipeline
            import torch

            logger.info(f"Loading fallback HF LLM: {settings.llm_hf_model_name}")
            device = 0 if torch.cuda.is_available() else -1
            
            _hf_pipeline = pipeline(
                "text-generation",
                model=settings.llm_hf_model_name,
                device=device,
                torch_dtype=torch.float16 if device == 0 else torch.float32,
                trust_remote_code=True,
            )
            _hf_loaded = True
            logger.info("Fallback HF LLM loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load fallback HF LLM: {e}")
            _hf_loaded = True


def is_llm_loaded() -> bool:
    """Check if either Ollama or HF is available."""
    # Check Ollama
    try:
        r = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=2)
        if r.status_code == 200:
            return True
    except requests.RequestException:
        pass
    
    # Check HF fallback
    return _hf_loaded and _hf_pipeline is not None


# ── Prompt templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a precise technical assistant for industrial machinery.
Your job is to answer questions based ONLY on the provided manual excerpts.

CRITICAL RULES:
1. If the answer is in the context, provide a clear, step-by-step explanation.
2. You MUST cite the source for your information using this format:
   [Manual Name > Chapter Name > Section Name, Page X]
3. If the context does not contain enough information, say "The provided manuals do not contain information to answer this query."
4. Do NOT invent specifications, values, or procedures.
5. Use technical language appropriate for maintenance engineers and operators."""


CLASSIFY_PROMPT = """Determine if the following user message requires looking up information from machine manuals.

Reply with exactly one word:
- "RETRIEVE" if the user is asking a technical question about machinery, procedures, specifications, maintenance, safety, or operations.
- "DIRECT" if the user is making a greeting, small talk, or a question that doesn't need manual lookup.

User message: {question}

Classification:"""


VALIDATE_PROMPT = """You are a grounding validator. Given a question, context excerpts from manuals, and a generated answer, determine if the answer is faithfully grounded in the provided context.

Rules:
- The answer must be supported by information in the context.
- Invented specifications, values, procedures, or facts NOT in the context = FAIL.
- Partial answers that are at least partially grounded = PARTIAL.
- Answers that clearly come from the context = PASS.

Context:
{context}

Question: {question}

Answer: {answer}

Reply with exactly one word: PASS, PARTIAL, or FAIL."""


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_chat_prompt(system: str, user: str) -> str:
    """Build a chat-template prompt (used for HF fallback)."""
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )


def build_prompt(question: str, context_chunks: list[dict]) -> str:
    """Build the main RAG user prompt text (without system prompt wrapper)."""
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        # Use rich hierarchical metadata
        path = chunk.get("hierarchy_path", "")
        page = chunk.get("page", "?")
        source_header = f"Source {i}: [{path}, Page {page}]"
        
        context_parts.append(f"{source_header}\n{chunk['text']}")
        
    context_str = "\n\n---\n\n".join(context_parts)

    user_msg = (
        f"Context from machine manuals:\n\n{context_str}\n\n"
        f"Question: {question}"
    )
    return user_msg


# ── Ollama execution ──────────────────────────────────────────────────────────

def _run_ollama(
    prompt_text: str,
    system_text: str = "",
    max_tokens: int = settings.llm_max_new_tokens,
) -> Optional[str]:
    """Execute query against Ollama HTTP API."""
    url = f"{settings.ollama_base_url}/api/generate"
    
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt_text,
        "system": system_text,
        "stream": False,
        "options": {
            "temperature": settings.llm_temperature,
            "num_predict": max_tokens,
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.RequestException as e:
        logger.warning(f"Ollama inference failed: {e}")
        return None


def _stream_ollama(
    prompt_text: str,
    system_text: str = "",
) -> Generator[str, None, None]:
    """Stream response from Ollama HTTP API."""
    url = f"{settings.ollama_base_url}/api/generate"
    
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt_text,
        "system": system_text,
        "stream": True,
        "options": {
            "temperature": settings.llm_temperature,
            "num_predict": settings.llm_max_new_tokens,
        }
    }
    
    try:
        with requests.post(url, json=payload, stream=True, timeout=60) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    yield data.get("response", "")
    except requests.RequestException as e:
        logger.warning(f"Ollama streaming failed: {e}")
        # Signal failure to fallback
        yield "__OLLAMA_FAILED__"


# ── HF Fallback execution ─────────────────────────────────────────────────────

def _run_hf(prompt: str, max_tokens: int = None) -> Optional[str]:
    """Run fallback HF pipeline."""
    if not _hf_loaded:
        _load_hf_pipeline()
    if _hf_pipeline is None:
        return None

    try:
        output = _hf_pipeline(
            prompt,
            max_new_tokens=max_tokens or settings.llm_max_new_tokens,
            temperature=settings.llm_temperature,
            do_sample=settings.llm_temperature > 0,
            pad_token_id=_hf_pipeline.tokenizer.eos_token_id,
            eos_token_id=_hf_pipeline.tokenizer.convert_tokens_to_ids("<|im_end|>"),
        )
        generated = output[0]["generated_text"]
        answer = generated[len(prompt):].strip()
        answer = answer.split("<|im_end|>")[0].strip()
        return answer
    except Exception as e:
        logger.error(f"HF inference error: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def classify_query(question: str) -> str:
    """Classify whether a query needs retrieval."""
    prompt = CLASSIFY_PROMPT.format(question=question)
    sys_msg = "You are a query classifier. Reply with exactly one word."
    
    # Try Ollama
    result = _run_ollama(prompt, system_text=sys_msg, max_tokens=10)
    
    # Try HF Fallback
    if result is None and settings.llm_fallback_enabled:
        full_prompt = _build_chat_prompt(sys_msg, prompt)
        result = _run_hf(full_prompt, max_tokens=10)
        
    if result:
        result = result.strip().upper()
        if "DIRECT" in result:
            return "DIRECT"
    return "RETRIEVE"  # default to retrieval for safety


def generate_answer(question: str, context_chunks: list[dict]) -> str:
    """Generate an answer from context chunks."""
    user_prompt = build_prompt(question, context_chunks)
    
    # Try Ollama
    result = _run_ollama(user_prompt, system_text=SYSTEM_PROMPT)
    
    # Try HF Fallback
    if result is None and settings.llm_fallback_enabled:
        full_prompt = _build_chat_prompt(SYSTEM_PROMPT, user_prompt)
        result = _run_hf(full_prompt)
        
    if result:
        return result
    return _fallback_answer(question, context_chunks)


def generate_direct_answer(question: str) -> str:
    """Generate a direct answer without retrieval."""
    sys_msg = (
        "You are a helpful assistant for industrial machine manual queries. "
        "Respond briefly and helpfully. If the user greets you, greet them back."
    )
    
    # Try Ollama
    result = _run_ollama(question, system_text=sys_msg, max_tokens=256)
    
    # Try HF Fallback
    if result is None and settings.llm_fallback_enabled:
        full_prompt = _build_chat_prompt(sys_msg, question)
        result = _run_hf(full_prompt, max_tokens=256)
        
    if result:
        return result
    return "Hello! I'm your machine manual assistant. Ask me any question."


def validate_answer(question: str, context_chunks: list[dict], answer: str) -> str:
    """Validate if the generated answer is grounded in the context."""
    context_str = "\n\n".join(
        f"[{c['hierarchy_path']}, Page {c.get('page', '?')}]: {c['text'][:400]}"
        for c in context_chunks[:5]
    )
    prompt = VALIDATE_PROMPT.format(context=context_str, question=question, answer=answer)
    sys_msg = "You are a grounding validator. Reply with exactly one word: PASS, PARTIAL, or FAIL."
    
    # Try Ollama
    result = _run_ollama(prompt, system_text=sys_msg, max_tokens=10)
    
    # Try HF Fallback
    if result is None and settings.llm_fallback_enabled:
        full_prompt = _build_chat_prompt(sys_msg, prompt)
        result = _run_hf(full_prompt, max_tokens=10)
        
    if result:
        result = result.strip().upper()
        if "PASS" in result:
            return "PASS"
        if "PARTIAL" in result:
            return "PARTIAL"
        if "FAIL" in result:
            return "FAIL"
    return "PASS"  # default to pass if validation fails to run


def generate_stream(question: str, context_chunks: list[dict]) -> Generator[str, None, None]:
    """Stream tokens from Ollama (or fallback to HF full generation)."""
    user_prompt = build_prompt(question, context_chunks)
    
    # Try Ollama stream
    ollama_failed = False
    for token in _stream_ollama(user_prompt, system_text=SYSTEM_PROMPT):
        if token == "__OLLAMA_FAILED__":
            ollama_failed = True
            break
        yield token
        
    # If Ollama failed, try HF fallback (non-streaming)
    if ollama_failed and settings.llm_fallback_enabled:
        full_prompt = _build_chat_prompt(SYSTEM_PROMPT, user_prompt)
        result = _run_hf(full_prompt)
        if result:
            yield result
        else:
            yield _fallback_answer(question, context_chunks)


def _fallback_answer(question: str, context_chunks: list[dict]) -> str:
    """Extractive fallback when LLMs are not available."""
    if not context_chunks:
        return "No relevant information found in the uploaded manuals for your query."

    parts = ["Based on the manual excerpts, here is the relevant information:\n"]
    for chunk in context_chunks[:3]:
        page = chunk.get("page", "?")
        path = chunk.get("hierarchy_path", chunk.get("filename", ""))
        parts.append(f"\n**From [{path}, Page {page}]:**\n{chunk['text'][:500]}…")
        
    parts.append("\n\n*Note: The AI model is currently unavailable. This is a direct excerpt.*")
    return "\n".join(parts)
