"""Input and model-response validation helpers."""
import json
import re


class InputError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


REQUIRED_TOP = ("topic", "difficulty", "content_overview", "technique", "technique_reason", "mnemonic", "key_facts", "memory_tips", "recall_test", "accuracy_notes")


def validate_source(text: object, max_chars: int) -> str:
    if not isinstance(text, str) or not text.strip():
        raise InputError("Add some text or upload a document before generating a mnemonic.")
    value = text.strip()
    if len(value) > max_chars:
        raise InputError(f"This source has {len(value):,} characters. The current limit is {max_chars:,}; split it into smaller sections.", 413)
    if len(value) < 20:
        raise InputError("Please provide at least 20 characters so MemoMind has enough context to identify and map the facts.")
    return value


def _string(value, label, minimum=1):
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise ValueError(f"The generated {label} is missing or invalid.")
    return value.strip()


def parse_and_validate_response(raw: str) -> dict:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I)
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Gemini returned malformed JSON.") from exc
    if not isinstance(data, dict) or any(k not in data for k in REQUIRED_TOP):
        raise ValueError("Gemini's response did not include all required sections.")
    for key in ("topic", "difficulty", "content_overview", "technique", "technique_reason"):
        data[key] = _string(data[key], key)
    mnemonic = data["mnemonic"]
    if not isinstance(mnemonic, dict):
        raise ValueError("The mnemonic section is invalid.")
    for key in ("title", "text"):
        mnemonic[key] = _string(mnemonic.get(key), f"mnemonic {key}")
    breakdown = mnemonic.get("breakdown")
    if not isinstance(breakdown, list) or not breakdown:
        raise ValueError("The mnemonic breakdown is missing.")
    for item in breakdown:
        if not isinstance(item, dict):
            raise ValueError("A mnemonic breakdown entry is invalid.")
        for key in ("component", "meaning", "explanation"):
            item[key] = _string(item.get(key), f"breakdown {key}")
    facts = data["key_facts"]
    if not isinstance(facts, list) or not facts or len(facts) > 40:
        raise ValueError("The key facts section is missing or too large.")
    for fact in facts:
        if not isinstance(fact, dict):
            raise ValueError("A key fact entry is invalid.")
        for key in ("fact", "explanation"):
            fact[key] = _string(fact.get(key), f"key fact {key}")
        if not isinstance(fact.get("keywords"), list) or not all(isinstance(k, str) for k in fact["keywords"]):
            raise ValueError("A key fact keyword list is invalid.")
    if not isinstance(data["memory_tips"], list) or not data["memory_tips"] or not all(isinstance(t, str) and t.strip() for t in data["memory_tips"]):
        raise ValueError("Memory tips are missing or invalid.")
    if not isinstance(data["accuracy_notes"], list) or not all(isinstance(n, str) for n in data["accuracy_notes"]):
        raise ValueError("Accuracy notes are invalid.")
    questions = data["recall_test"]
    if not isinstance(questions, list) or not 3 <= len(questions) <= 8:
        raise ValueError("The recall test must contain between 3 and 8 questions.")
    for q in questions:
        if not isinstance(q, dict) or q.get("type") not in ("mcq", "fill_blank", "short_answer"):
            raise ValueError("A recall question has an unsupported type.")
        q["question"] = _string(q.get("question"), "recall question")
        q["correct_answer"] = _string(q.get("correct_answer"), "recall answer")
        q["explanation"] = _string(q.get("explanation"), "recall explanation")
        if q["type"] == "mcq":
            options = q.get("options")
            if not isinstance(options, list) or len(options) != 4 or not all(isinstance(o, str) for o in options) or q["correct_answer"] not in options:
                raise ValueError("A multiple-choice question has invalid options or answer.")
        else:
            q["options"] = []
            acceptable = q.get("acceptable_answers", [])
            if not isinstance(acceptable, list) or not all(isinstance(a, str) for a in acceptable):
                raise ValueError("A recall answer alias list is invalid.")
            q["acceptable_answers"] = acceptable
    return data
