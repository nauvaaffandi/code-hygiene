# Engine package - code quality detectors for Code Hygiene.
from code_hygiene.engine.base import Detector, Finding
from code_hygiene.engine.checkers import FileSizeChecker, DirectoryChecker
from code_hygiene.engine.duplicate import DuplicateChecker
from code_hygiene.engine.dead_code import DeadCodeChecker
from code_hygiene.engine.generation import AbstractionChecker, GenerationChecker
from code_hygiene.engine.changes import ChangesChecker
from code_hygiene.engine.policy import PolicyEngine
from code_hygiene.engine.confidence import (
    CONFIRMED,
    LIKELY,
    SUSPECTED,
    UNSUPPORTED,
    is_actionable,
    is_high_confidence,
    severity_from_confidence,
)

__all__ = [
    "Detector",
    "Finding",
    "FileSizeChecker",
    "DirectoryChecker",
    "DuplicateChecker",
    "DeadCodeChecker",
    "AbstractionChecker",
    "GenerationChecker",
    "ChangesChecker",
    "PolicyEngine",
    "CONFIRMED",
    "LIKELY",
    "SUSPECTED",
    "UNSUPPORTED",
    "is_actionable",
    "is_high_confidence",
    "severity_from_confidence",
]