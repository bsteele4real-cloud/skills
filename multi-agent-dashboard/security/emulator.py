"""Docker-based emulator sandbox for secure link verification."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio
import hashlib
import re


class RiskLevel(Enum):
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    BLOCKED = 5


@dataclass
class NetworkRequest:
    url: str
    method: str
    status_code: Optional[int]
    content_type: Optional[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EmulatorResult:
    url: str
    final_url: str
    title: Optional[str]
    screenshot_path: Optional[str]
    network_requests: List[NetworkRequest]
    redirect_chain: List[str]
    javascript_errors: List[str]
    load_time_ms: int
    risk_indicators: List[str]
    safe: bool
    risk_level: RiskLevel
    error: Optional[str] = None


@dataclass
class EmulatorConfig:
    headless: bool = True
    sandbox: bool = True
    disable_javascript: bool = False
    timeout_ms: int = 30000
    max_redirects: int = 5
    capture_screenshot: bool = True
    monitor_network: bool = True
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"


class ThreatSignatures:
    """Known threat patterns and signatures."""

    # Malicious URL patterns
    URL_PATTERNS = [
        r"bit\.ly/[a-zA-Z0-9]+$",  # Shortened URLs (need verification)
        r"tinyurl\.com",
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",  # IP addresses
        r"[a-z0-9]{32,}\.xyz$",  # Suspicious domains
        r"login.*\.(?!com|org|net|gov)",  # Phishing patterns
        r"secure-.*verify",
        r"account-.*update",
    ]

    # Suspicious JavaScript patterns
    JS_PATTERNS = [
        r"eval\s*\(",
        r"document\.write\s*\(",
        r"atob\s*\(",
        r"fromCharCode",
        r"crypto\.subtle",
        r"keylogger",
        r"clipboard",
    ]

    # Dangerous content types
    DANGEROUS_CONTENT_TYPES = [
        "application/x-msdownload",
        "application/x-executable",
        "application/x-sh",
        "application/x-bat",
    ]

    # Known malicious domains (sample - real implementation would use threat feeds)
    BLOCKED_DOMAINS = [
        "malware.com",
        "phishing-site.net",
    ]


class EmulatorSandbox:
    """Sandboxed browser emulator for link verification."""

    def __init__(self, config: Optional[EmulatorConfig] = None):
        self.config = config or EmulatorConfig()
        self.signatures = ThreatSignatures()
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Pre-compile regex patterns for efficiency."""
        return {
            "url": [re.compile(p, re.IGNORECASE) for p in self.signatures.URL_PATTERNS],
            "js": [re.compile(p, re.IGNORECASE) for p in self.signatures.JS_PATTERNS],
        }

    async def verify_link(self, url: str) -> EmulatorResult:
        """Verify link safety in sandboxed environment."""
        risk_indicators = []
        redirect_chain = [url]

        # Step 1: Static URL analysis
        static_risk = self._analyze_url_static(url)
        if static_risk.level >= RiskLevel.CRITICAL:
            return EmulatorResult(
                url=url,
                final_url=url,
                title=None,
                screenshot_path=None,
                network_requests=[],
                redirect_chain=redirect_chain,
                javascript_errors=[],
                load_time_ms=0,
                risk_indicators=static_risk.indicators,
                safe=False,
                risk_level=RiskLevel.CRITICAL,
                error="Blocked by static analysis",
            )

        risk_indicators.extend(static_risk.indicators)

        # Step 2: DNS and SSL verification (simulated)
        dns_result = await self._verify_dns_ssl(url)
        risk_indicators.extend(dns_result.get("indicators", []))

        # Step 3: Emulator-based dynamic analysis
        try:
            emulator_result = await self._emulate_visit(url)
            risk_indicators.extend(emulator_result.get("risk_indicators", []))
            redirect_chain = emulator_result.get("redirect_chain", [url])

            # Step 4: Content analysis
            content_risk = self._analyze_content(emulator_result)
            risk_indicators.extend(content_risk)

        except asyncio.TimeoutError:
            return EmulatorResult(
                url=url,
                final_url=url,
                title=None,
                screenshot_path=None,
                network_requests=[],
                redirect_chain=redirect_chain,
                javascript_errors=[],
                load_time_ms=self.config.timeout_ms,
                risk_indicators=risk_indicators + ["Timeout during page load"],
                safe=False,
                risk_level=RiskLevel.HIGH,
                error="Timeout",
            )
        except Exception as e:
            return EmulatorResult(
                url=url,
                final_url=url,
                title=None,
                screenshot_path=None,
                network_requests=[],
                redirect_chain=redirect_chain,
                javascript_errors=[],
                load_time_ms=0,
                risk_indicators=risk_indicators + [f"Error: {str(e)}"],
                safe=False,
                risk_level=RiskLevel.MEDIUM,
                error=str(e),
            )

        # Calculate overall risk
        risk_level = self._calculate_risk_level(risk_indicators)

        return EmulatorResult(
            url=url,
            final_url=emulator_result.get("final_url", url),
            title=emulator_result.get("title"),
            screenshot_path=emulator_result.get("screenshot_path"),
            network_requests=emulator_result.get("network_requests", []),
            redirect_chain=redirect_chain,
            javascript_errors=emulator_result.get("js_errors", []),
            load_time_ms=emulator_result.get("load_time_ms", 0),
            risk_indicators=risk_indicators,
            safe=risk_level.value <= RiskLevel.LOW.value,
            risk_level=risk_level,
        )

    def _analyze_url_static(self, url: str) -> "StaticAnalysisResult":
        """Analyze URL without visiting it."""
        indicators = []

        # Check against blocked domains
        for domain in self.signatures.BLOCKED_DOMAINS:
            if domain in url.lower():
                return StaticAnalysisResult(
                    level=RiskLevel.BLOCKED,
                    indicators=[f"Blocked domain: {domain}"],
                )

        # Check URL patterns
        for pattern in self._compiled_patterns["url"]:
            if pattern.search(url):
                indicators.append(f"Suspicious URL pattern: {pattern.pattern}")

        # Check for data URIs
        if url.startswith("data:"):
            indicators.append("Data URI detected")
            return StaticAnalysisResult(level=RiskLevel.HIGH, indicators=indicators)

        # Check for javascript URIs
        if url.lower().startswith("javascript:"):
            indicators.append("JavaScript URI detected")
            return StaticAnalysisResult(level=RiskLevel.CRITICAL, indicators=indicators)

        # Check URL length (very long URLs can be suspicious)
        if len(url) > 2000:
            indicators.append("Unusually long URL")

        # Determine risk level from indicators
        if len(indicators) >= 3:
            level = RiskLevel.HIGH
        elif len(indicators) >= 1:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return StaticAnalysisResult(level=level, indicators=indicators)

    async def _verify_dns_ssl(self, url: str) -> Dict[str, Any]:
        """Verify DNS and SSL certificate."""
        indicators = []

        # In production, this would:
        # 1. Resolve DNS and check for suspicious records
        # 2. Verify SSL certificate validity
        # 3. Check certificate issuer
        # 4. Detect DNS poisoning indicators

        # Simulated checks
        if not url.startswith("https://"):
            indicators.append("Non-HTTPS URL")

        return {"indicators": indicators}

    async def _emulate_visit(self, url: str) -> Dict[str, Any]:
        """Visit URL in sandboxed browser."""
        # In production, this would use Playwright or Puppeteer in Docker
        # to actually visit the URL in a sandboxed environment

        # Simulated response
        start_time = datetime.utcnow()

        # Simulate network activity
        network_requests = [
            NetworkRequest(
                url=url,
                method="GET",
                status_code=200,
                content_type="text/html",
            )
        ]

        load_time_ms = 500  # Simulated

        return {
            "final_url": url,
            "title": "Page Title",
            "screenshot_path": None,
            "network_requests": network_requests,
            "redirect_chain": [url],
            "js_errors": [],
            "load_time_ms": load_time_ms,
            "risk_indicators": [],
            "page_content": "",
        }

    def _analyze_content(self, emulator_result: Dict[str, Any]) -> List[str]:
        """Analyze page content for threats."""
        indicators = []
        content = emulator_result.get("page_content", "")

        # Check for suspicious JavaScript
        for pattern in self._compiled_patterns["js"]:
            if pattern.search(content):
                indicators.append(f"Suspicious JS pattern: {pattern.pattern}")

        # Check network requests
        for req in emulator_result.get("network_requests", []):
            if isinstance(req, NetworkRequest):
                if req.content_type in self.signatures.DANGEROUS_CONTENT_TYPES:
                    indicators.append(f"Dangerous download: {req.content_type}")

        # Check redirect count
        redirects = emulator_result.get("redirect_chain", [])
        if len(redirects) > self.config.max_redirects:
            indicators.append(f"Excessive redirects: {len(redirects)}")

        return indicators

    def _calculate_risk_level(self, indicators: List[str]) -> RiskLevel:
        """Calculate overall risk level from indicators."""
        if not indicators:
            return RiskLevel.SAFE

        # Weight certain indicators more heavily
        critical_keywords = ["blocked", "malware", "phishing", "javascript uri"]
        high_keywords = ["suspicious", "dangerous", "excessive"]

        critical_count = sum(
            1 for ind in indicators
            if any(kw in ind.lower() for kw in critical_keywords)
        )
        high_count = sum(
            1 for ind in indicators
            if any(kw in ind.lower() for kw in high_keywords)
        )

        if critical_count > 0:
            return RiskLevel.CRITICAL
        elif high_count >= 2:
            return RiskLevel.HIGH
        elif high_count >= 1 or len(indicators) >= 3:
            return RiskLevel.MEDIUM
        elif len(indicators) >= 1:
            return RiskLevel.LOW
        return RiskLevel.SAFE


@dataclass
class StaticAnalysisResult:
    level: RiskLevel
    indicators: List[str]


async def verify_url_safe(url: str) -> bool:
    """Convenience function to check if URL is safe."""
    emulator = EmulatorSandbox()
    result = await emulator.verify_link(url)
    return result.safe


def get_url_hash(url: str) -> str:
    """Get hash of URL for caching/logging."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]
