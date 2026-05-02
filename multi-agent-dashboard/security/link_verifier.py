"""Link verification pipeline with multi-stage security checks."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timedelta
import asyncio
import re
from urllib.parse import urlparse

from .emulator import EmulatorSandbox, EmulatorResult, RiskLevel


class VerificationStatus(Enum):
    PENDING = "pending"
    VERIFIED_SAFE = "verified_safe"
    VERIFIED_UNSAFE = "verified_unsafe"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class DomainReputation:
    domain: str
    reputation_score: float  # 0-100
    category: str
    first_seen: datetime
    is_new: bool
    ssl_valid: bool
    whois_age_days: int
    known_threats: List[str]


@dataclass
class VerificationResult:
    url: str
    status: VerificationStatus
    risk_level: RiskLevel
    emulator_result: Optional[EmulatorResult]
    domain_reputation: Optional[DomainReputation]
    checks_passed: List[str]
    checks_failed: List[str]
    warnings: List[str]
    verification_time_ms: int
    requires_team_vote: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LinkVerifier:
    """Multi-stage link verification pipeline."""

    # Allowlisted domains (trusted by default)
    TRUSTED_DOMAINS = {
        "google.com", "github.com", "stackoverflow.com",
        "microsoft.com", "apple.com", "amazon.com",
        "wikipedia.org", "anthropic.com", "openai.com",
    }

    # Known dangerous TLDs
    SUSPICIOUS_TLDS = {
        ".xyz", ".top", ".work", ".click", ".loan",
        ".download", ".win", ".stream", ".gdn",
    }

    def __init__(self):
        self.emulator = EmulatorSandbox()
        self._cache: Dict[str, VerificationResult] = {}
        self._cache_ttl = timedelta(hours=24)

    async def verify(
        self,
        url: str,
        skip_cache: bool = False,
        require_team_vote_for_edge_cases: bool = True,
    ) -> VerificationResult:
        """Full verification pipeline for a URL."""
        start_time = datetime.utcnow()
        checks_passed = []
        checks_failed = []
        warnings = []

        # Check cache first
        if not skip_cache:
            cached = self._get_cached(url)
            if cached:
                return cached

        # Parse URL
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception as e:
            return self._error_result(url, f"Invalid URL: {e}", start_time)

        # Stage 1: Quick domain checks
        domain_result = await self._check_domain(domain)

        if domain_result["trusted"]:
            checks_passed.append("Trusted domain")
            # Fast path for trusted domains
            result = VerificationResult(
                url=url,
                status=VerificationStatus.VERIFIED_SAFE,
                risk_level=RiskLevel.SAFE,
                emulator_result=None,
                domain_reputation=domain_result.get("reputation"),
                checks_passed=checks_passed,
                checks_failed=[],
                warnings=[],
                verification_time_ms=self._calc_time(start_time),
                requires_team_vote=False,
            )
            self._cache_result(url, result)
            return result

        if domain_result["blocked"]:
            checks_failed.append("Domain blocked")
            return VerificationResult(
                url=url,
                status=VerificationStatus.BLOCKED,
                risk_level=RiskLevel.BLOCKED,
                emulator_result=None,
                domain_reputation=domain_result.get("reputation"),
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                warnings=[],
                verification_time_ms=self._calc_time(start_time),
                requires_team_vote=False,
            )

        # Stage 2: URL pattern analysis
        url_analysis = self._analyze_url_patterns(url, parsed)
        checks_passed.extend(url_analysis["passed"])
        checks_failed.extend(url_analysis["failed"])
        warnings.extend(url_analysis["warnings"])

        # Stage 3: Protocol checks
        if parsed.scheme != "https":
            warnings.append("Non-HTTPS URL")
        else:
            checks_passed.append("HTTPS protocol")

        # Stage 4: Emulator sandbox verification
        emulator_result = await self.emulator.verify_link(url)

        if emulator_result.safe:
            checks_passed.append("Emulator verification passed")
        else:
            checks_failed.append("Emulator verification failed")
            checks_failed.extend(emulator_result.risk_indicators)

        # Determine final status
        status, requires_vote = self._determine_status(
            checks_passed,
            checks_failed,
            warnings,
            emulator_result,
            require_team_vote_for_edge_cases,
        )

        result = VerificationResult(
            url=url,
            status=status,
            risk_level=emulator_result.risk_level,
            emulator_result=emulator_result,
            domain_reputation=domain_result.get("reputation"),
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
            verification_time_ms=self._calc_time(start_time),
            requires_team_vote=requires_vote,
        )

        self._cache_result(url, result)
        return result

    async def _check_domain(self, domain: str) -> Dict[str, Any]:
        """Check domain reputation and trust level."""
        # Check if trusted
        for trusted in self.TRUSTED_DOMAINS:
            if domain == trusted or domain.endswith("." + trusted):
                return {
                    "trusted": True,
                    "blocked": False,
                    "reputation": DomainReputation(
                        domain=domain,
                        reputation_score=95.0,
                        category="trusted",
                        first_seen=datetime(2000, 1, 1),
                        is_new=False,
                        ssl_valid=True,
                        whois_age_days=9999,
                        known_threats=[],
                    ),
                }

        # Check TLD
        for tld in self.SUSPICIOUS_TLDS:
            if domain.endswith(tld):
                return {
                    "trusted": False,
                    "blocked": False,
                    "reputation": DomainReputation(
                        domain=domain,
                        reputation_score=30.0,
                        category="suspicious_tld",
                        first_seen=datetime.utcnow(),
                        is_new=True,
                        ssl_valid=True,
                        whois_age_days=30,
                        known_threats=["Suspicious TLD"],
                    ),
                }

        # Default: unknown domain, needs verification
        return {
            "trusted": False,
            "blocked": False,
            "reputation": DomainReputation(
                domain=domain,
                reputation_score=50.0,
                category="unknown",
                first_seen=datetime.utcnow(),
                is_new=True,
                ssl_valid=True,
                whois_age_days=365,
                known_threats=[],
            ),
        }

    def _analyze_url_patterns(
        self,
        url: str,
        parsed: Any,
    ) -> Dict[str, List[str]]:
        """Analyze URL for suspicious patterns."""
        passed = []
        failed = []
        warnings = []

        # Check for IP address instead of domain
        ip_pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
        if ip_pattern.match(parsed.netloc):
            failed.append("URL uses IP address instead of domain")

        # Check for suspicious port
        if parsed.port and parsed.port not in [80, 443, 8080, 8443]:
            warnings.append(f"Unusual port: {parsed.port}")

        # Check for encoded characters in path
        if "%00" in url or "%0a" in url.lower():
            failed.append("Null byte or newline injection in URL")

        # Check for excessive path depth
        path_depth = len([p for p in parsed.path.split("/") if p])
        if path_depth > 10:
            warnings.append(f"Deep URL path: {path_depth} levels")

        # Check for suspicious query parameters
        query = parsed.query.lower()
        if "redirect" in query or "url=" in query or "next=" in query:
            warnings.append("Redirect parameter in URL")

        # Check for base64 encoded data
        if re.search(r"[A-Za-z0-9+/]{50,}={0,2}", url):
            warnings.append("Possible base64 encoded data in URL")

        if not failed and not warnings:
            passed.append("URL pattern analysis passed")

        return {"passed": passed, "failed": failed, "warnings": warnings}

    def _determine_status(
        self,
        passed: List[str],
        failed: List[str],
        warnings: List[str],
        emulator_result: EmulatorResult,
        require_vote: bool,
    ) -> tuple[VerificationStatus, bool]:
        """Determine final verification status."""
        # Critical failure
        if emulator_result.risk_level in [RiskLevel.CRITICAL, RiskLevel.BLOCKED]:
            return VerificationStatus.BLOCKED, False

        # Clear failures
        if len(failed) >= 2 or emulator_result.risk_level == RiskLevel.HIGH:
            return VerificationStatus.VERIFIED_UNSAFE, False

        # Clear success
        if not failed and not warnings and emulator_result.safe:
            return VerificationStatus.VERIFIED_SAFE, False

        # Edge case: some warnings, needs review
        if warnings and require_vote:
            return VerificationStatus.NEEDS_REVIEW, True

        # Default to safe with warnings
        if emulator_result.safe:
            return VerificationStatus.VERIFIED_SAFE, False

        return VerificationStatus.NEEDS_REVIEW, require_vote

    def _get_cached(self, url: str) -> Optional[VerificationResult]:
        """Get cached verification result if valid."""
        if url not in self._cache:
            return None

        result = self._cache[url]
        age = datetime.utcnow() - result.timestamp

        if age > self._cache_ttl:
            del self._cache[url]
            return None

        return result

    def _cache_result(self, url: str, result: VerificationResult) -> None:
        """Cache verification result."""
        self._cache[url] = result

        # Limit cache size
        if len(self._cache) > 10000:
            # Remove oldest entries
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k].timestamp,
            )
            for key in sorted_keys[:1000]:
                del self._cache[key]

    def _error_result(
        self,
        url: str,
        error: str,
        start_time: datetime,
    ) -> VerificationResult:
        """Create error result."""
        return VerificationResult(
            url=url,
            status=VerificationStatus.ERROR,
            risk_level=RiskLevel.MEDIUM,
            emulator_result=None,
            domain_reputation=None,
            checks_passed=[],
            checks_failed=[error],
            warnings=[],
            verification_time_ms=self._calc_time(start_time),
            requires_team_vote=False,
        )

    def _calc_time(self, start: datetime) -> int:
        """Calculate elapsed time in milliseconds."""
        return int((datetime.utcnow() - start).total_seconds() * 1000)

    def clear_cache(self) -> int:
        """Clear verification cache. Returns count of cleared entries."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get verifier statistics."""
        status_counts = {}
        for result in self._cache.values():
            status = result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "cache_size": len(self._cache),
            "cache_ttl_hours": self._cache_ttl.total_seconds() / 3600,
            "trusted_domains": len(self.TRUSTED_DOMAINS),
            "status_counts": status_counts,
        }


async def verify_link(url: str) -> VerificationResult:
    """Convenience function for quick link verification."""
    verifier = LinkVerifier()
    return await verifier.verify(url)


async def is_link_safe(url: str) -> bool:
    """Quick check if link is safe."""
    result = await verify_link(url)
    return result.status == VerificationStatus.VERIFIED_SAFE
