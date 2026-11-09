"""Small deterministic stages. They organize work; they do not claim model-level reasoning."""
from __future__ import annotations
import re
from collections.abc import Callable
from pandoria.reasoning.contracts import ReasoningContext, ReasoningPlan, Subtask


def normalize(text: str) -> str:
    return re.sub(r"\\s+", " ", text).strip()


def classify_intent(text: str) -> str:
    value = text.casefold()
    groups = {
        "research": ("investiga", "research", "fuentes", "actualidad", "latest", "compara"),
        "build": ("construye", "crea", "implementa", "build", "code", "programa"),
        "plan": ("planifica", "organiza", "itinerario", "roadmap", "plan"),
        "explain": ("explica", "qué es", "como funciona", "how does", "why"),
        "creative": ("escribe", "diseña", "idea", "inventa", "write", "create"),
    }
    for intent, terms in groups.items():
        if any(term in value for term in terms):
            return intent
    return "general"


def estimate_complexity(text: str) -> str:
    words = len(text.split())
    conjunctions = sum(text.casefold().count(term) for term in
                       (" y ", " además ", " también ", " then ", " and "))
    if words > 100 or conjunctions >= 4:
        return "high"
    if words > 35 or conjunctions >= 2:
        return "medium"
    return "low"


def extract_constraints(text: str) -> tuple[str, ...]:
    patterns = (
        r"\\b(?:sin|no|evita|excepto)\\b[^.!?;]*",
        r"\\b(?:antes de|después de|máximo|mínimo|presupuesto)\\b[^.!?;]*",
        r"\\b\\d+\\s*(?:segundos|minutos|horas|días|weeks|days)\\b",
    )
    found: list[str] = []
    for pattern in patterns:
        found.extend(match.group(0).strip() for match in re.finditer(pattern, text, re.I))
    return tuple(dict.fromkeys(found))


def decompose(context: ReasoningContext) -> tuple[Subtask, ...]:
    if context.complexity == "low":
        return (Subtask("solve", context.normalized_request, "solve"),)
    if context.intent == "research":
        return (
            Subtask("scope", "Define the question, scope, and freshness requirements.", "analysis"),
            Subtask("gather", "Collect reliable evidence for the scoped question.", "research", ("scope",), frozenset({"web.search"})),
            Subtask("synthesize", "Compare evidence, resolve conflicts, and answer with citations.", "synthesis", ("gather",)),
        )
    if context.intent == "build":
        return (
            Subtask("specify", "Extract requirements, constraints, and acceptance criteria.", "analysis"),
            Subtask("design", "Design modular components, interfaces, and failure boundaries.", "design", ("specify",)),
            Subtask("implement", "Implement the smallest coherent working increment.", "implementation", ("design",)),
            Subtask("verify", "Run or define tests and inspect edge cases.", "verification", ("implement",)),
        )
    return (
        Subtask("analyze", "Identify the goal, constraints, assumptions, and unknowns.", "analysis"),
        Subtask("solve", "Develop a solution that satisfies the identified constraints.", "solve", ("analyze",)),
        Subtask("review", "Check consistency, omissions, and unsupported claims.", "verification", ("solve",)),
    )


Stage = Callable[[str], object]
