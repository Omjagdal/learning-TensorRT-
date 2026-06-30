"""
llm/qwen_service.py — Ollama HTTP integration for Qwen3 + HF Fallback.

Primary: Ollama HTTP API (http://localhost:11434/api/generate) with qwen:8b
Fallback: HuggingFace Transformers Pipeline (kept for local execution)
"""

from __future__ import annotations

import base64
import json
import threading
from pathlib import Path
from typing import Generator, Optional

import requests
from loguru import logger

from app.core.config import get_settings

settings = get_settings()

# ── Ollama HTTP session (connection pooling / keep-alive) ─────────────────────
_ollama_session: requests.Session | None = None


def _get_ollama_session() -> requests.Session:
    """Get or create a persistent HTTP session for Ollama calls."""
    global _ollama_session
    if _ollama_session is None:
        _ollama_session = requests.Session()
        # Connection pooling: reuse TCP connections to Ollama
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=2,
            pool_maxsize=4,
            max_retries=1,
        )
        _ollama_session.mount("http://", adapter)
    return _ollama_session

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
            import torch
            from transformers import pipeline

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
    # Check Ollama (via pooled session)
    try:
        session = _get_ollama_session()
        r = session.get(f"{settings.ollama_base_url}/api/tags", timeout=2)
        if r.status_code == 200:
            return True
    except requests.RequestException:
        pass

    # Check HF fallback
    return _hf_loaded and _hf_pipeline is not None


# ── Prompt templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are ISRA Vision Chatbot Assistant, a technical assistant for industrial machine manuals.

⚠️ CRITICAL RULE: You MUST answer EXCLUSIVELY from the manual context excerpts provided below. Do NOT use your general world knowledge. Every fact, step, value, or procedure in your answer MUST come directly from the provided manual context.

RULES:
1. MANUAL-GROUNDED ONLY: Base your entire answer on the "Context from machine manuals" section.
2. MISSING CONTEXT (CRITICAL): If the context lacks relevant information, you MUST output EXACTLY: "The provided manual does not contain information about this topic."
   HOWEVER, if the user explicitly asked for a "diagram", "image", "picture", or "schematic", DO NOT output that error message. Instead, simply explain whatever related procedural steps or technical details you can find in the context.
3. IMAGE TEXT VERIFICATION (CRITICAL): If the prompt includes text extracted from a user's image, you MUST compare it against the provided manual context. If the extracted text (e.g., error codes, labels) is NOT found in the context, you MUST NOT generate an answer. Instead, output EXACTLY: "The text extracted from the image was not found in the database."
4. DO NOT INVENT: Never make up specifications, values, procedures, part numbers, or settings that are not explicitly stated in the context.
5. OPERATOR-FRIENDLY TONE: The answers must be easy to understand for a machine operator on the factory floor. Use clear, accessible, and practical language. Avoid overly dense academic jargon unless quoting a specific part name or setting.
6. CHATGPT-LIKE FORMATTING: Format your responses cleanly and simply:
   - Use strict Markdown headings (e.g., ### Heading Name) for sections. Do NOT just use bold text for section titles.
   - Use standard bulleted (-) or numbered (1.) lists for procedures.
   - **TABLES**: If the question asks for technical specifications, limits, parameters, or comparisons (like the bead width limits), you MUST present the data as a Markdown table.
   - Use **bold text** for emphasis, but ensure you properly close all markdown tags (e.g., **like this**).
   - Use horizontal dividers (---) to separate distinct sections.
6. APPROPRIATE LENGTH & DEPTH: Scale the length and depth of your answer to exactly match what the user is asking. 
   - If they ask a simple, specific question (e.g., "What is the bead width?"), give a concise, direct answer. Do NOT generate unnecessary filler.
   - If they ask a broad or complex question (e.g., "Explain how the system works" or "How do I teach the camera?"), provide a comprehensive, step-by-step breakdown covering the mechanism, components, safety, and procedures.
   - Always ensure the answer is fully complete but never artificially padded.
7. PROVIDE EXAMPLES: Generate concrete, practical examples based on the user's query. 
   - Keep the examples extremely simple, practical, and easy for an operator to understand.
   - Do NOT scatter examples throughout the text.
   - FORMAT EXAMPLES AS TABLES: If the example involves parameters, measurements, specifications, or numerical values, present it as a clean Markdown table with a "Parameter" column and a "Specification" or "Value" column.
   - For procedural or scenario-based examples, use a short numbered list.
   - Aggregate the example(s) and place them ONLY at the end of your response, in their own section under a "### Example" heading, immediately BEFORE the conclusion.
8. ASCII DIAGRAMS: Generate a strictly linear, single-column ASCII text diagram/flowchart for ALMOST ALL queries to map out logic, concepts, or steps. 
   - Keep it extremely simple. Do NOT attempt horizontal branching, parallel columns, or complex layouts.
   - Use vertical pipes and arrows in a ```text code block, like:
      [Concept A]
           |
           v
      [Concept B]
   - Try to include this diagram for most explanations to visually aid the operator.
   - Place the diagram after your text explanation but before the examples and conclusion.
9. DO NOT append "Manual Reference", source citations, or list the sources used at the end of your answer. The UI already displays the sources automatically.
10. CONCLUSION: Always conclude your technical responses with a brief, helpful summary or wrap-up statement under a "### Conclusion" heading."""


CLASSIFY_PROMPT = """You are a query router for an industrial machine manual chatbot.

The chatbot has access to technical manuals for industrial machines, inspection systems, and equipment.

Reply with exactly one word:
- "DIRECT" ONLY if the message is a pure greeting, farewell, or social small talk with absolutely NO technical intent:
  Examples of DIRECT: "hello", "hi there", "thanks", "goodbye", "what is your name", "who made you"
- "RETRIEVE" for ANY other message — including questions that seem general but could relate to the product:
  Examples of RETRIEVE: "how does this work", "what is camera", "show me steps", "what is RTV", "how to calibrate", "explain the system", "what are the settings", "teach me", "installation", "error", "manual", "operation"

When in doubt, always choose RETRIEVE. It is always safer to retrieve context from the manual.

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
        f"Context from machine manuals:\n\n{context_str}\n\n" f"Question: {question}"
    )
    return user_msg


# ── Ollama execution ──────────────────────────────────────────────────────────


def _run_ollama(
    prompt_text: str,
    system_text: str = "",
    max_tokens: int = settings.llm_max_new_tokens,
    images: Optional[list[str]] = None,
) -> Optional[str]:
    """Execute query against Ollama HTTP API."""
    url = f"{settings.ollama_base_url}/api/generate"

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt_text,
        "system": system_text,
        "stream": False,
        "think": False,  # Disable Qwen3 thinking mode — returns empty without this
        "options": {
            "temperature": settings.llm_temperature,
            "num_predict": max_tokens,
        },
    }
    if images:
        payload["images"] = images

    try:
        # 600s timeout for CPU inference (Qwen3:8b is very slow on CPU)
        session = _get_ollama_session()
        response = session.post(url, json=payload, timeout=600)
        response.raise_for_status()
        result = response.json().get("response", "").strip()
        return result if result else None
    except requests.RequestException as e:
        logger.warning(f"Ollama inference failed: {e}")
        return None


def _stream_ollama(
    prompt_text: str,
    system_text: str = "",
    images: Optional[list[str]] = None,
    model: Optional[str] = None,
) -> Generator[str, None, None]:
    """Stream response from Ollama HTTP API."""
    url = f"{settings.ollama_base_url}/api/generate"

    use_model = model or settings.ollama_model

    payload = {
        "model": use_model,
        "prompt": prompt_text,
        "system": system_text,
        "stream": True,
        "think": False,  # Disable Qwen3 thinking mode — returns empty without this
        "options": {
            "temperature": settings.llm_temperature,
            "num_predict": settings.llm_max_new_tokens,
        },
    }
    if images:
        payload["images"] = images

    try:
        # 600s timeout for streaming (Qwen3:8b on CPU can be very slow for prompt eval)
        timeout = 600
        session = _get_ollama_session()
        with session.post(url, json=payload, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:  # Skip empty tokens from think mode
                        yield token
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
        answer = generated[len(prompt) :].strip()
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


def _run_ollama_vlm(
    prompt_text: str,
    system_text: str = "",
    max_tokens: int = 512,
    images: Optional[list[str]] = None,
) -> Optional[str]:
    """Execute a query against Ollama using the VLM model (for vision tasks)."""
    url = f"{settings.ollama_base_url}/api/generate"

    payload = {
        "model": settings.ollama_vlm_model,
        "prompt": prompt_text,
        "system": system_text,
        "stream": False,
        "think": False,  # Disable thinking mode for Qwen3-VL too
        "options": {
            "temperature": 0.1,  # Low temp for accurate technical captions
            "num_predict": max_tokens,
        },
    }
    if images:
        payload["images"] = images

    try:
        # 240s timeout — VLM image processing is slow on CPU
        session = _get_ollama_session()
        response = session.post(url, json=payload, timeout=240)
        response.raise_for_status()
        result = response.json().get("response", "").strip()
        return result if result else None
    except requests.RequestException as e:
        logger.warning(f"Ollama VLM inference failed: {e}")
        return None


def is_vlm_available() -> bool:
    """Check if the VLM model is available in Ollama."""
    try:
        session = _get_ollama_session()
        r = session.get(f"{settings.ollama_base_url}/api/tags", timeout=2)
        if r.status_code == 200:
            models = r.json().get("models", [])
            vlm_name = settings.ollama_vlm_model.split(":")[0]
            return any(vlm_name in m.get("name", "") for m in models)
    except requests.RequestException:
        pass
    return False


def generate_caption_for_image(image_path: Path) -> str:
    """Generate a detailed technical caption for an image using qwen3-vl:8b."""
    try:
        with open(image_path, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")
        return generate_caption_for_base64_image(b64_image)
    except Exception as e:
        logger.error(f"Failed to generate caption for {image_path}: {e}")
    return ""

def generate_caption_for_base64_image(b64_image: str) -> str:
    """Extract text from a base64 image using PaddleOCR."""
    try:
        import numpy as np
        import cv2
        from paddleocr import PaddleOCR

        # Initialize PaddleOCR
        ocr = PaddleOCR(use_textline_orientation=True, lang='en')
        
        # Remove data URI prefix if present
        if "," in b64_image:
            b64_image = b64_image.split(",")[1]
            
        # Fix incorrect padding
        b64_image += "=" * ((4 - len(b64_image) % 4) % 4)
        
        # Decode base64 to image
        img_data = base64.b64decode(b64_image)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            logger.error("Failed to decode base64 image for PaddleOCR")
            return ""

        # Run OCR
        result = ocr.ocr(img)
        
        extracted_text = []
        if result and len(result) > 0:
            res = result[0]
            # Handle new PaddleX OCRResult format
            if hasattr(res, 'get') and res.get('rec_texts'):
                extracted_text = res.get('rec_texts')
            elif isinstance(res, dict) and 'rec_texts' in res:
                extracted_text = res['rec_texts']
            # Fallback to older list-of-lists format
            elif isinstance(res, list):
                for line in res:
                    try:
                        if isinstance(line, (list, tuple)) and len(line) > 1:
                            text = line[1][0]
                            extracted_text.append(text)
                    except Exception:
                        pass
                
        final_text = " ".join(extracted_text)
        if final_text:
            logger.debug(f"PaddleOCR extracted text: {final_text[:80]}...")
            return final_text

        logger.warning(f"PaddleOCR returned empty text for base64 image")
    except Exception as e:
        logger.error(f"Failed to run PaddleOCR on base64 image: {e}")
    return ""


def generate_answer(
    question: str, context_chunks: list[dict], has_images: bool = False
) -> str:
    """Generate an answer from context chunks using qwen3:8b (text model).
    
    NOTE: Always uses qwen3:8b regardless of whether images are present.
    Retrieved manual images are displayed to the user in the UI,
    but are NOT sent to the LLM. Text chunks provide all the context needed.
    """
    user_prompt = build_prompt(question, context_chunks)
    
    if has_images:
        user_prompt += "\n\n[SYSTEM NOTE: Diagram images matching the user's query HAVE BEEN SUCCESSFULLY RETRIEVED AND DISPLAYED on the screen. DO NOT say the manual lacks information. Simply summarize any relevant technical context or steps available.]"

    # Always use text model (qwen3:8b) — never use VLM for answer generation
    result = _run_ollama(user_prompt, system_text=SYSTEM_PROMPT, images=None)

    # Try HF Fallback
    if result is None and settings.llm_fallback_enabled:
        full_prompt = _build_chat_prompt(SYSTEM_PROMPT, user_prompt)
        result = _run_hf(full_prompt)

    if result:
        return result
    return "I am currently offline or unable to connect to the language model. Please ensure Ollama or the fallback AI service is running."



def generate_direct_answer(question: str) -> str:
    """Generate a direct answer without retrieval."""
    sys_msg = (
        "You are a helpful, interactive assistant for industrial machine manuals. "
        "Respond briefly and engagingly using emojis. If the user greets you, greet them back warmly! 👋"
    )

    # Try Ollama
    result = _run_ollama(question, system_text=sys_msg, max_tokens=256)

    # Try HF Fallback
    if result is None and settings.llm_fallback_enabled:
        full_prompt = _build_chat_prompt(sys_msg, question)
        result = _run_hf(full_prompt, max_tokens=256)

    if result:
        return result
    return "Hello! 👋 I'm your interactive machine manual assistant. Ask me any question, and I'll find the answer for you! 🤖✨"


def validate_answer(question: str, context_chunks: list[dict], answer: str) -> str:
    """Validate if the generated answer is grounded in the context."""
    context_str = "\n\n".join(
        f"[{c['hierarchy_path']}, Page {c.get('page', '?')}]: {c['text']}"
        for c in context_chunks[:5]
    )
    prompt = VALIDATE_PROMPT.format(
        context=context_str, question=question, answer=answer
    )
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


def generate_stream(
    question: str, context_chunks: list[dict], has_images: bool = False
) -> Generator[str, None, None]:
    """Stream tokens from Ollama using qwen3:8b (text model).
    
    NOTE: Always uses qwen3:8b regardless of whether images are present.
    Retrieved manual page images are displayed to the user in the UI,
    but are NOT sent to the LLM. The text chunks provide all the context
    the LLM needs to generate accurate, detailed answers.
    """
    user_prompt = build_prompt(question, context_chunks)

    if has_images:
        user_prompt += "\n\n[SYSTEM NOTE: Diagram images matching the user's query HAVE BEEN SUCCESSFULLY RETRIEVED AND DISPLAYED on the screen. DO NOT say the manual lacks information. Simply summarize any relevant technical context or steps available.]"

    # Always use text model (qwen3:8b) — never switch to VLM for answering
    # qwen3-vl:8b produces poor answers; qwen3:8b has full context from text chunks
    logger.info(f"Streaming answer with text model ({settings.ollama_model})")

    ollama_failed = False
    for token in _stream_ollama(
        user_prompt, system_text=SYSTEM_PROMPT,
        images=None, model=None,  # Always text model, no images passed
    ):
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
            yield _extractive_fallback(question, context_chunks)


def _extractive_fallback(question: str, context_chunks: list[dict]) -> str:
    """Extractive fallback when LLMs are not available."""
    if not context_chunks:
        return (
            "No relevant information found in the uploaded manuals for your query. 😔"
        )

    parts = [
        "### 📄 Relevant Manual Excerpts\nBased on the manual excerpts, here is the relevant information:\n"
    ]
    for chunk in context_chunks[:5]:
        page = chunk.get("page", "?")
        path = chunk.get("hierarchy_path", chunk.get("filename", ""))
        parts.append(f"\n**📌 From [{path}, Page {page}]:**\n> {chunk['text']}\n")

    parts.append(
        "\n\n*⚠️ Note: The AI model is currently unavailable. This is a direct excerpt from the text.*"
    )
    return "\n".join(parts)
