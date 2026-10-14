# Confidence levels for findings, from strongest to weakest evidence.
#
#   confirmed   - direct measurement or structural equivalence (AST, line count, etc.)
#   likely      - normalized similarity with clear evidence (e.g., token Jaccard)
#   suspected   - heuristic or pattern-based; must be inspected before acting
#   unsupported - analysis not available for the target language


CONFIRMED = "confirmed"
LIKELY = "likely"
SUSPECTED = "suspected"
UNSUPPORTED = "unsupported"

CONFIDENCE_SCORES = {
    CONFIRMED: 4,
    LIKELY: 3,
    SUSPECTED: 2,
    UNSUPPORTED: 0,
}


def is_actionable(confidence: str) -> bool:
    """True if the agent should act (not just inspect) on this finding."""
    return confidence in (CONFIRMED, LIKELY)


def is_high_confidence(confidence: str) -> bool:
    """True for confident findings (used for report summary and exit codes)."""
    return confidence in (CONFIRMED, LIKELY)


def severity_from_confidence(confidence: str) -> str:
    """Map confidence to a display severity when severity is unavailable."""
    return {CONFIRMED: "HIGH", LIKELY: "MEDIUM", SUSPECTED: "LOW", UNSUPPORTED: "INFO"}.get(
        confidence, "INFO"
    )