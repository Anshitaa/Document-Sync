"""
Google Gemini LLM + Vision client for documentation generation and UI change analysis.
Uses the google.generativeai package with multimodal support.
"""

import os
import io
import json
import logging
import PIL.Image
import google.generativeai as genai
from dotenv import load_dotenv
from rag import build_rag_context

# Load environment variables
load_dotenv()

logger = logging.getLogger("docu-sync.llm")


class GeminiClient:
    """Client for Google Gemini API — supports text and vision (multimodal) inputs."""

    def __init__(self):
        # REQUIRED: Set GEMINI_API_KEY in your .env file
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        # Configure Gemini
        genai.configure(api_key=self.api_key)

        # Single model instance used for both text and vision tasks
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

    # ── Internal helper ────────────────────────────────────────────────────────

    def _generate(self, parts: list, max_tokens: int = 500) -> str:
        """Send a list of content parts (text and/or images) to Gemini."""
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.7,
            top_p=0.9,
        )
        response = self.model.generate_content(
            parts,
            generation_config=generation_config,
        )
        try:
            if hasattr(response, 'text') and response.text:
                return response.text.strip()
        except ValueError:
            if response.candidates and response.candidates[0].content.parts:
                texts = [p.text for p in response.candidates[0].content.parts if hasattr(p, 'text')]
                if texts:
                    return ' '.join(texts).strip()
        return ""

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """
        Robustly extract a JSON object from a Gemini response.
        Handles markdown code fences (```json ... ```) and bare JSON.
        """
        text = raw.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop first line (``` or ```json) and last line (```)
            text = "\n".join(lines[1:-1]).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Last resort: find the first { ... } block
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end + 1])
            raise

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze_visual_changes(self, old_bytes: bytes, new_bytes: bytes) -> dict:
        """
        Use Gemini Vision to semantically describe what changed between two UI screenshots.

        Args:
            old_bytes: bytes of the original (before) screenshot
            new_bytes: bytes of the updated (after) screenshot

        Returns:
            dict with keys:
                - changed_elements: list[str]  — specific UI elements that changed
                - semantic_summary: str         — plain-English 1-2 sentence summary
                - change_type: str              — layout | color | text | component_added |
                                                  component_removed | mixed
                - severity: str                 — minor | moderate | significant
        """
        old_img = PIL.Image.open(io.BytesIO(old_bytes))
        new_img = PIL.Image.open(io.BytesIO(new_bytes))

        prompt = (
            "You are a senior UI/UX analyst reviewing a product update.\n\n"
            "The FIRST image is the BEFORE state. The SECOND image is the AFTER state.\n\n"
            "Carefully compare the two screenshots and return a JSON object with exactly "
            "these fields (return ONLY the JSON, no extra text or markdown):\n"
            "{\n"
            '  "changed_elements": ["specific UI change 1", "specific UI change 2", ...],\n'
            '  "semantic_summary": "1-2 sentence plain-English summary of what changed",\n'
            '  "change_type": "one of: layout | color | text | component_added | component_removed | mixed",\n'
            '  "severity": "one of: minor | moderate | significant"\n'
            "}\n\n"
            "Be specific in changed_elements — e.g. "
            "'Submit button color changed from blue to green' not just 'button changed'."
        )

        logger.info("Sending image pair to Gemini Vision for semantic analysis")
        raw = self._generate([prompt, old_img, new_img], max_tokens=600)

        try:
            result = self._parse_json_response(raw)
            logger.info(
                "Vision analysis complete: type=%s severity=%s elements=%d",
                result.get("change_type", "?"),
                result.get("severity", "?"),
                len(result.get("changed_elements", [])),
            )
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Could not parse vision JSON response, using fallback: %s", e)
            # Graceful fallback so the endpoint never breaks
            return {
                "changed_elements": [],
                "semantic_summary": raw[:300] if raw else "Vision analysis unavailable.",
                "change_type": "mixed",
                "severity": "moderate",
            }

    def generate_documentation(self, change_summary: str, current_readme: str = "") -> dict:
        """
        Generate updated README content with confidence score and reasoning.

        Uses a RAG pipeline to retrieve the most semantically relevant sections
        of the existing README before generating — producing far more accurate
        context-aware documentation than naive truncation.

        Args:
            change_summary: description of detected changes (from detect-change)
            current_readme: optional full README content for RAG retrieval

        Returns:
            dict with keys:
                - documentation:    str   — the generated documentation text (2-3 sentences)
                - confidence:       float — 0.0–1.0 model confidence score
                - reasoning:        str   — explanation of the documentation choices made
                - rag_headings:     list  — README sections retrieved by RAG
                - rag_chunks_used:  int   — number of chunks retrieved
        """
        # RAG: retrieve the most relevant README sections for this change
        rag = build_rag_context(change_summary, current_readme, top_k=3)
        rag_context = rag["context"]
        rag_context_label = (
            f"Most relevant README sections (retrieved by semantic search — "
            f"{rag['chunks_retrieved']} of {rag['total_chunks']} chunks):\n{rag_context}"
            if rag_context
            else "No existing README provided."
        )

        prompt = (
            "You are a technical documentation assistant updating a software README.\n\n"
            f"UI changes detected:\n{change_summary}\n\n"
            f"{rag_context_label}\n\n"
            "Write an updated documentation entry for these changes. "
            "Return a JSON object with exactly these fields "
            "(return ONLY the JSON, no extra text or markdown):\n"
            "{\n"
            '  "documentation": "2-3 sentence professional update describing the change and its impact on users",\n'
            '  "confidence": 0.0,\n'
            '  "reasoning": "explanation of why you wrote the documentation this way — '
            "what context from the README you used, what you emphasised, "
            'and any assumptions you made"\n'
            "}\n\n"
            "For confidence: use 0.9+ if the changes are clear and the README context is highly relevant, "
            "0.7-0.9 if moderately clear, below 0.7 if vague or ambiguous.\n"
            "Return ONLY the JSON object."
        )

        logger.info(
            "Requesting structured documentation from Gemini "
            "(RAG: %d chunks retrieved, confidence + reasoning enabled)",
            rag["chunks_retrieved"],
        )
        raw = self._generate([prompt], max_tokens=700)

        try:
            result = self._parse_json_response(raw)
            result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.75))))
            # Attach RAG metadata to the result
            result["rag_headings"] = rag.get("headings", [])
            result["rag_chunks_used"] = rag.get("chunks_retrieved", 0)
            logger.info(
                "Documentation generated (confidence=%.2f, %d chars, RAG sections: %s)",
                result["confidence"],
                len(result.get("documentation", "")),
                result["rag_headings"],
            )
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Could not parse documentation JSON, using fallback: %s", e)
            return {
                "documentation": raw[:500].strip() if raw else "Documentation generation failed.",
                "confidence": 0.5,
                "reasoning": "Structured output parsing failed; raw text returned as documentation.",
                "rag_headings": rag.get("headings", []),
                "rag_chunks_used": rag.get("chunks_retrieved", 0),
            }

    def prompt_llm(self, prompt: str, max_tokens: int = 500) -> str:
        """
        Simple text-only prompt — kept for backward compatibility.

        Args:
            prompt: str, the input prompt
            max_tokens: int, maximum tokens to generate

        Returns:
            str: generated text response
        """
        try:
            return self._generate([prompt], max_tokens=max_tokens)
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")


# ── Singleton helpers ──────────────────────────────────────────────────────────

_client = None


def get_client() -> GeminiClient:
    """Get or create the global GeminiClient instance."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


def prompt_llm(prompt: str, max_tokens: int = 500) -> str:
    """Convenience wrapper — text-only prompt."""
    return get_client().prompt_llm(prompt, max_tokens)


def analyze_visual_changes(old_bytes: bytes, new_bytes: bytes) -> dict:
    """Convenience wrapper — Gemini Vision change analysis."""
    return get_client().analyze_visual_changes(old_bytes, new_bytes)


def generate_documentation(change_summary: str, current_readme: str = "") -> dict:
    """Convenience wrapper — structured documentation generation."""
    return get_client().generate_documentation(change_summary, current_readme)
