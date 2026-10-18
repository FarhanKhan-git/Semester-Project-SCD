"""
ai_engine.py
Question generation and answer grading.

IMPORTANT: This is a PLACEHOLDER version that works offline with simple
keyword rules, so the whole system can be demonstrated before the Gemini API
is connected. Later, only the two functions below will be replaced with
Gemini calls. Nothing else in the project needs to change.

    generate_question(chunk_text, difficulty, avoid) -> question string
    grade_answer(answer, chunk_text)                 -> {score, verdict, reason}
"""

import re
from collections import Counter

STOP_WORDS = set("""
a an the and or but if then than so of to in on at by for with from into onto
is are was were be been being am do does did done has have had having this that
these those it its they them their there here which who whom whose what when
where why how all any both each few more most other some such no nor not only own
same too very can will just should could would may might must also as about above
below between through during before after again further once our we you your he
she his her i me my us one two three use used using many much within without
often usually because every whether while like make makes made part parts example
document chapter section figure table page introduction
""".split())


def stem(word: str) -> str:
    """Very simple stemming so that 'testing', 'tests' and 'test' all match."""
    for ending in ("ing", "ed", "es", "s"):
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[: -len(ending)]
    return word


def words_of(text: str):
    return [w for w in re.findall(r"[a-z][a-z\-]{2,}", text.lower()) if w not in STOP_WORDS]


def keywords(text: str, top: int = 8):
    """The most frequent meaningful word stems in a piece of text."""
    return [w for w, _ in Counter(stem(w) for w in words_of(text)).most_common(top)]


def topics(text: str):
    """Candidate topics for a question: repeated two-word phrases first
    (e.g. 'branch coverage'), then single important words."""
    words = words_of(text)
    pairs = Counter(f"{a} {b}" for a, b in zip(words, words[1:]) if a != b)
    phrases = [p for p, n in pairs.most_common() if n >= 2]
    singles = [w for w, _ in Counter(words).most_common(10) if len(w) > 4]
    return phrases + singles


def generate_question(chunk_text: str, difficulty: str, avoid=()) -> str:
    # TODO (Week 9): replace with a Gemini call that is given ONLY chunk_text.
    used = " ".join(avoid).lower()
    options = [t for t in topics(chunk_text) if t not in used] or topics(chunk_text) or ["this section"]
    topic = options[0]

    if difficulty == "Easy":
        return f"According to the document, what is {topic}?"
    if difficulty == "Hard" and len(options) >= 2:
        return f"Compare {topic} with {options[1]}, using the points given in the document."
    return f"Explain {topic} as described in the document, and why it is important."


def grade_answer(answer: str, chunk_text: str) -> dict:
    # TODO (Week 11): replace with a Gemini call that compares the MEANING of
    # the answer with chunk_text using a fixed rubric.
    if not answer.strip():
        return {"score": 0, "verdict": "Incorrect", "reason": "No answer was given."}

    expected = keywords(chunk_text, 10)
    said = {stem(w) for w in words_of(answer)}
    matched = [k for k in expected if k in said]

    # 5 matching key points = full marks
    score = min(10, round(10 * len(matched) / 5))
    if score >= 7:
        verdict = "Correct"
    elif score >= 4:
        verdict = "Partially Correct"
    else:
        verdict = "Incorrect"

    missing = [k for k in expected if k not in said][:3]
    reason = ("Covered: " + ", ".join(matched[:5]) + ". ") if matched else ""
    if missing and score < 10:
        reason += "Could also mention: " + ", ".join(missing) + "."
    return {"score": score, "verdict": verdict, "reason": reason.strip()}
