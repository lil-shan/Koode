import json
import os

# Load knowledge base once
KB_PATH = os.path.join(os.path.dirname(__file__), "symptoms.json")
with open(KB_PATH, "r", encoding="utf-8") as f:
    KNOWLEDGE_BASE = json.load(f)

def retrieve(conversation_history: list) -> str:
    """
    Look at last 3 patient messages, find matching symptom chunks,
    return a compact clinical context string to inject into the prompt.
    """
    # Extract recent patient messages
    recent_text = " ".join([
        m["content"].lower()
        for m in conversation_history[-6:]
        if m["role"] == "user"
    ])

    matched = []
    for symptom, data in KNOWLEDGE_BASE.items():
        if symptom == "general":
            continue
        keywords = data.get("keywords", [])
        if any(kw.lower() in recent_text for kw in keywords):
            matched.append((symptom, data))

    # Always include general if nothing matched
    if not matched:
        matched.append(("general", KNOWLEDGE_BASE["general"]))

    # Build compact context string
    context_parts = []
    for symptom, data in matched[:2]:  # max 2 chunks to keep context small
        part = f"[{symptom.upper()}]\n"
        if data.get("red_flags"):
            part += "RED FLAGS: " + " | ".join(data["red_flags"][:3]) + "\n"
        if data.get("associated_to_check"):
            part += "ASK ABOUT: " + ", ".join(data["associated_to_check"][:5]) + "\n"
        if data.get("kerala_context"):
            part += "KERALA CONTEXT: " + data["kerala_context"][0] + "\n"
        if data.get("clinical_notes"):
            part += "CLINICAL NOTE: " + data["clinical_notes"] + "\n"
        context_parts.append(part)

    return "\n".join(context_parts)


def get_follow_up_hint(conversation_history: list) -> str:
    """Get suggested next question based on current symptom."""
    recent_text = " ".join([
        m["content"].lower()
        for m in conversation_history[-4:]
        if m["role"] == "user"
    ])

    for symptom, data in KNOWLEDGE_BASE.items():
        if symptom == "general":
            continue
        keywords = data.get("keywords", [])
        if any(kw.lower() in recent_text for kw in keywords):
            questions = data.get("follow_up_questions", [])
            if questions:
                # Return first unanswered question
                return questions[0]
    return ""
