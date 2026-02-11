import json
import re


def safe_json_loads(text: str) -> dict:
    """
    Safely parse LLM JSON output.
    Strips code fences, handles common LLM formatting issues.
    """
    if not text:
        raise ValueError("Empty LLM response")

    cleaned = text.strip()

    # Remove markdown code fences if present
    if cleaned.startswith("```"):
        # Handle ```json\n...\n``` pattern
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        else:
            # Fallback: split by backticks
            parts = cleaned.split("```")
            if len(parts) >= 2:
                cleaned = parts[1].strip()
                # Remove language hint
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()

    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}\n\nRaw text:\n{text[:500]}")
