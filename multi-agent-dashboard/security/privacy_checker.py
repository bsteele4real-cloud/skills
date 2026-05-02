"""Privacy compliance checking following GDPR, CCPA, and other frameworks."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime
import re


class ComplianceFramework(Enum):
    GDPR = "gdpr"
    CCPA = "ccpa"
    HIPAA = "hipaa"
    COPPA = "coppa"
    PCI_DSS = "pci_dss"


class ViolationSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PIIEntity:
    entity_type: str
    value: str
    start_pos: int
    end_pos: int
    confidence: float
    should_redact: bool = True


@dataclass
class Violation:
    framework: ComplianceFramework
    rule_id: str
    description: str
    severity: ViolationSeverity
    entity: Optional[PIIEntity]
    recommendation: str


@dataclass
class ComplianceResult:
    compliant: bool
    violations: List[Violation]
    entities_found: List[PIIEntity]
    frameworks_checked: List[ComplianceFramework]
    redacted_data: Optional[str]
    scan_time_ms: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PIIDetector:
    """Detect PII entities in text."""

    # Regex patterns for common PII
    PATTERNS = {
        "email": (
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            0.95,
        ),
        "phone_us": (
            r"\b(?:\+1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
            0.90,
        ),
        "ssn": (
            r"\b[0-9]{3}[-\s]?[0-9]{2}[-\s]?[0-9]{4}\b",
            0.85,
        ),
        "credit_card": (
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
            0.95,
        ),
        "ip_address": (
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            0.90,
        ),
        "date_of_birth": (
            r"\b(?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12][0-9]|3[01])[-/](?:19|20)\d{2}\b",
            0.80,
        ),
        "passport": (
            r"\b[A-Z]{1,2}[0-9]{6,9}\b",
            0.70,
        ),
        "driver_license": (
            r"\b[A-Z][0-9]{7,8}\b",
            0.60,
        ),
        "bank_account": (
            r"\b[0-9]{8,17}\b",  # Very broad, needs context
            0.50,
        ),
        "address": (
            r"\b\d{1,5}\s+[\w\s]+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|court|ct|boulevard|blvd)\b",
            0.75,
        ),
    }

    # Name patterns (simplified)
    NAME_PATTERN = r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"

    def __init__(self):
        self._compiled = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, (pattern, _) in self.PATTERNS.items()
        }
        self._name_pattern = re.compile(self.NAME_PATTERN)

    def detect(self, text: str) -> List[PIIEntity]:
        """Detect PII entities in text."""
        entities = []

        # Check each pattern
        for entity_type, pattern in self._compiled.items():
            confidence = self.PATTERNS[entity_type][1]

            for match in pattern.finditer(text):
                # Skip if likely false positive
                if self._is_false_positive(entity_type, match.group(), text):
                    continue

                entities.append(PIIEntity(
                    entity_type=entity_type,
                    value=match.group(),
                    start_pos=match.start(),
                    end_pos=match.end(),
                    confidence=confidence,
                ))

        # Sort by position
        entities.sort(key=lambda e: e.start_pos)

        return entities

    def _is_false_positive(
        self,
        entity_type: str,
        value: str,
        context: str,
    ) -> bool:
        """Check for common false positives."""
        # Bank account numbers that are too short
        if entity_type == "bank_account" and len(value) < 10:
            # Check if it's in a context suggesting it's a bank account
            idx = context.find(value)
            surrounding = context[max(0, idx-30):idx+len(value)+30].lower()
            if "account" not in surrounding and "routing" not in surrounding:
                return True

        # SSN patterns that are clearly dates
        if entity_type == "ssn":
            parts = re.split(r"[-\s]", value)
            if len(parts) == 3:
                # If it looks like a date, skip
                try:
                    if int(parts[0]) <= 12 and int(parts[1]) <= 31:
                        return True
                except ValueError:
                    pass

        return False

    def redact(
        self,
        text: str,
        entities: Optional[List[PIIEntity]] = None,
        replacement: str = "[REDACTED]",
    ) -> str:
        """Redact PII from text."""
        if entities is None:
            entities = self.detect(text)

        # Sort by position descending to replace from end
        sorted_entities = sorted(entities, key=lambda e: e.start_pos, reverse=True)

        result = text
        for entity in sorted_entities:
            if entity.should_redact:
                result = (
                    result[:entity.start_pos]
                    + f"{replacement}"
                    + result[entity.end_pos:]
                )

        return result


class PrivacyChecker:
    """Check data for privacy compliance."""

    # Framework-specific rules
    FRAMEWORK_RULES = {
        ComplianceFramework.GDPR: {
            "require_consent": ["email", "name", "phone_us", "address"],
            "special_category": ["health", "religion", "political"],
            "max_retention_days": 730,
        },
        ComplianceFramework.CCPA: {
            "require_disclosure": ["email", "name", "phone_us", "address", "ip_address"],
            "right_to_delete": True,
            "opt_out_sale": True,
        },
        ComplianceFramework.HIPAA: {
            "protected_health_info": [
                "ssn", "date_of_birth", "name", "address", "phone_us",
                "email", "ip_address", "medical_record",
            ],
            "encryption_required": True,
        },
        ComplianceFramework.COPPA: {
            "children_data": ["name", "email", "address", "phone_us"],
            "parental_consent_required": True,
            "age_verification": True,
        },
        ComplianceFramework.PCI_DSS: {
            "cardholder_data": ["credit_card", "name"],
            "encryption_required": True,
            "access_logging_required": True,
        },
    }

    def __init__(self):
        self.detector = PIIDetector()

    async def check_compliance(
        self,
        data: str,
        frameworks: Optional[List[ComplianceFramework]] = None,
        redact: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> ComplianceResult:
        """Check data for privacy compliance."""
        start_time = datetime.utcnow()
        context = context or {}

        frameworks = frameworks or list(ComplianceFramework)
        violations = []
        entities = self.detector.detect(data)

        for framework in frameworks:
            framework_violations = self._check_framework(
                framework, entities, context
            )
            violations.extend(framework_violations)

        # Redact if requested
        redacted_data = None
        if redact and entities:
            redacted_data = self.detector.redact(data, entities)

        scan_time_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )

        return ComplianceResult(
            compliant=len(violations) == 0,
            violations=violations,
            entities_found=entities,
            frameworks_checked=frameworks,
            redacted_data=redacted_data,
            scan_time_ms=scan_time_ms,
        )

    def _check_framework(
        self,
        framework: ComplianceFramework,
        entities: List[PIIEntity],
        context: Dict[str, Any],
    ) -> List[Violation]:
        """Check compliance for a specific framework."""
        violations = []
        rules = self.FRAMEWORK_RULES.get(framework, {})
        entity_types = {e.entity_type for e in entities}

        if framework == ComplianceFramework.GDPR:
            violations.extend(self._check_gdpr(entities, entity_types, context))
        elif framework == ComplianceFramework.CCPA:
            violations.extend(self._check_ccpa(entities, entity_types, context))
        elif framework == ComplianceFramework.HIPAA:
            violations.extend(self._check_hipaa(entities, entity_types, context))
        elif framework == ComplianceFramework.COPPA:
            violations.extend(self._check_coppa(entities, entity_types, context))
        elif framework == ComplianceFramework.PCI_DSS:
            violations.extend(self._check_pci_dss(entities, entity_types, context))

        return violations

    def _check_gdpr(
        self,
        entities: List[PIIEntity],
        entity_types: Set[str],
        context: Dict[str, Any],
    ) -> List[Violation]:
        """Check GDPR compliance."""
        violations = []
        rules = self.FRAMEWORK_RULES[ComplianceFramework.GDPR]

        # Check if personal data exists without consent
        if not context.get("has_consent", False):
            for entity_type in rules["require_consent"]:
                if entity_type in entity_types:
                    for entity in entities:
                        if entity.entity_type == entity_type:
                            violations.append(Violation(
                                framework=ComplianceFramework.GDPR,
                                rule_id="GDPR-6",
                                description=f"Personal data ({entity_type}) processed without consent",
                                severity=ViolationSeverity.HIGH,
                                entity=entity,
                                recommendation="Obtain explicit consent before processing personal data",
                            ))
                            break

        return violations

    def _check_ccpa(
        self,
        entities: List[PIIEntity],
        entity_types: Set[str],
        context: Dict[str, Any],
    ) -> List[Violation]:
        """Check CCPA compliance."""
        violations = []
        rules = self.FRAMEWORK_RULES[ComplianceFramework.CCPA]

        # Check if personal info requires disclosure
        if not context.get("privacy_notice_provided", False):
            for entity_type in rules["require_disclosure"]:
                if entity_type in entity_types:
                    violations.append(Violation(
                        framework=ComplianceFramework.CCPA,
                        rule_id="CCPA-1798.100",
                        description=f"Personal information ({entity_type}) collected without disclosure",
                        severity=ViolationSeverity.MEDIUM,
                        entity=None,
                        recommendation="Provide privacy notice at collection point",
                    ))
                    break

        return violations

    def _check_hipaa(
        self,
        entities: List[PIIEntity],
        entity_types: Set[str],
        context: Dict[str, Any],
    ) -> List[Violation]:
        """Check HIPAA compliance."""
        violations = []
        rules = self.FRAMEWORK_RULES[ComplianceFramework.HIPAA]

        # Check for PHI without encryption
        if not context.get("is_encrypted", False):
            for entity_type in rules["protected_health_info"]:
                if entity_type in entity_types:
                    violations.append(Violation(
                        framework=ComplianceFramework.HIPAA,
                        rule_id="HIPAA-164.312",
                        description=f"Protected health information ({entity_type}) not encrypted",
                        severity=ViolationSeverity.CRITICAL,
                        entity=None,
                        recommendation="Encrypt all PHI at rest and in transit",
                    ))
                    break

        return violations

    def _check_coppa(
        self,
        entities: List[PIIEntity],
        entity_types: Set[str],
        context: Dict[str, Any],
    ) -> List[Violation]:
        """Check COPPA compliance."""
        violations = []

        # Only applicable if dealing with children's data
        if not context.get("involves_children", False):
            return violations

        rules = self.FRAMEWORK_RULES[ComplianceFramework.COPPA]

        if not context.get("parental_consent", False):
            for entity_type in rules["children_data"]:
                if entity_type in entity_types:
                    violations.append(Violation(
                        framework=ComplianceFramework.COPPA,
                        rule_id="COPPA-312.5",
                        description=f"Children's personal information ({entity_type}) without parental consent",
                        severity=ViolationSeverity.CRITICAL,
                        entity=None,
                        recommendation="Obtain verifiable parental consent before collecting children's data",
                    ))
                    break

        return violations

    def _check_pci_dss(
        self,
        entities: List[PIIEntity],
        entity_types: Set[str],
        context: Dict[str, Any],
    ) -> List[Violation]:
        """Check PCI-DSS compliance."""
        violations = []
        rules = self.FRAMEWORK_RULES[ComplianceFramework.PCI_DSS]

        # Check for cardholder data without encryption
        if "credit_card" in entity_types:
            if not context.get("is_encrypted", False):
                violations.append(Violation(
                    framework=ComplianceFramework.PCI_DSS,
                    rule_id="PCI-DSS-3.4",
                    description="Cardholder data not encrypted",
                    severity=ViolationSeverity.CRITICAL,
                    entity=None,
                    recommendation="Encrypt all cardholder data using strong cryptography",
                ))

            if not context.get("access_logged", False):
                violations.append(Violation(
                    framework=ComplianceFramework.PCI_DSS,
                    rule_id="PCI-DSS-10.2",
                    description="Cardholder data access not logged",
                    severity=ViolationSeverity.HIGH,
                    entity=None,
                    recommendation="Implement audit logging for all access to cardholder data",
                ))

        return violations


async def check_privacy(
    data: str,
    redact: bool = True,
) -> ComplianceResult:
    """Convenience function for quick privacy check."""
    checker = PrivacyChecker()
    return await checker.check_compliance(data, redact=redact)


def redact_pii(text: str) -> str:
    """Quick function to redact PII from text."""
    detector = PIIDetector()
    return detector.redact(text)
