from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib


@dataclass
class Finding:
    """A single detected issue with evidence, confidence, and recommended action."""
    id: str
    category: str
    sub_category: str
    path: str
    severity: str
    confidence: str
    metric: int
    threshold: str
    action: str
    evidence: str
    detection_method: str
    first_seen: str
    last_seen: str
    related_paths: List[str] = field(default_factory=list)
    rule_id: str = ""  # Stable identity: category:sub_category:normalized_location

    @classmethod
    def create(
        cls,
        category: str,
        sub_category: str,
        path: str,
        severity: str,
        confidence: str,
        metric: int,
        threshold: str,
        action: str,
        evidence: str,
        detection_method: str,
        related_paths: Optional[List[str]] = None,
        rule_id: Optional[str] = None,
    ) -> "Finding":
        now = datetime.now().isoformat()
        # Generate stable rule_id if not provided
        if rule_id is None:
            # Create deterministic identity from category, sub_category, path, and metric
            identity_parts = f"{category}:{sub_category}:{path}:{metric}"
            rule_id = hashlib.sha256(identity_parts.encode()).hexdigest()[:16]
        return cls(
            id=f"{category}:{path}:{sub_category}",
            category=category,
            sub_category=sub_category,
            path=path,
            severity=severity,
            confidence=confidence,
            metric=metric,
            threshold=threshold,
            action=action,
            evidence=evidence,
            detection_method=detection_method,
            first_seen=now,
            last_seen=now,
            related_paths=related_paths or [],
            rule_id=rule_id,
        )


class Detector:
    """Abstract base class for all code-hygiene detectors."""

    name: str
    supported_languages: List[str]
    description: str

    def scan(
        self, repo_root: Path, ignore_engine: Any, config: Dict[str, Any]
    ) -> List[Finding]:
        raise NotImplementedError