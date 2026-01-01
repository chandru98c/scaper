"""
World Model Module
==================
Internal representation of the environment for the CareerBoard agent.

This module implements the agent's "memory" - maintaining beliefs about:
1. Target website states (threat levels, capabilities)
2. Historical performance per strategy
3. DOM selector memory for adaptive extraction
4. Rate limiting awareness

The World Model enables:
- Model-based reasoning about environment state
- Learning from past interactions
- Adaptive behavior based on site characteristics

Reference: Russell & Norvig (2021) - "Artificial Intelligence: A Modern Approach"
           Chapter 2: Model-Based Reflex Agents
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from enum import Enum
from datetime import datetime
import json
import os


class SiteCapability(Enum):
    """
    Detected capabilities of a target website.
    
    These capabilities influence strategy selection:
    - SITEMAP_AVAILABLE: Prefer sitemap crawling
    - PAGINATION_DETECTED: Auto-discovery viable
    - API_AVAILABLE: Direct API extraction possible
    - JAVASCRIPT_REQUIRED: Need browser automation
    - AUTHENTICATED_ONLY: Skip or handle auth
    """
    SITEMAP_AVAILABLE = "sitemap_available"
    SITEMAP_XML = "sitemap_xml"
    SITEMAP_HTML = "sitemap_html"
    PAGINATION_DETECTED = "pagination_detected"
    INFINITE_SCROLL = "infinite_scroll"
    API_AVAILABLE = "api_available"
    JAVASCRIPT_REQUIRED = "js_required"
    AUTHENTICATED_ONLY = "authenticated_only"
    CLOUDFLARE_PROTECTED = "cloudflare_protected"
    CAPTCHA_PRESENT = "captcha_present"


class ThreatLevel(Enum):
    """
    Threat assessment for rate limiting/blocking risk.
    
    Higher levels trigger more conservative behavior:
    - NONE: Normal operation
    - LOW: Minor delays observed
    - MEDIUM: 429s encountered, increase delays
    - HIGH: Multiple 429s, rotate identity
    - BLOCKED: 403 received, switch strategy
    """
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    BLOCKED = 4
    
    def get_recommended_delay(self) -> float:
        """Get recommended delay in seconds for this threat level."""
        delays = {
            ThreatLevel.NONE: 3.0,
            ThreatLevel.LOW: 5.0,
            ThreatLevel.MEDIUM: 10.0,
            ThreatLevel.HIGH: 30.0,
            ThreatLevel.BLOCKED: 60.0
        }
        return delays.get(self, 5.0)


@dataclass
class SelectorMemory:
    """
    Memory of CSS/XPath selectors that worked for a site.
    
    Enables adaptive extraction when layouts change:
    - Stores successful selectors with timestamps
    - Falls back to alternatives when primary fails
    """
    # Primary selectors (most recently successful)
    article_container: Optional[str] = None
    job_link: Optional[str] = None
    next_page: Optional[str] = None
    date_element: Optional[str] = None
    apply_button: Optional[str] = None
    
    # Alternative selectors (fallbacks)
    alternatives: Dict[str, List[str]] = field(default_factory=dict)
    
    # Success tracking
    success_count: Dict[str, int] = field(default_factory=dict)
    last_success: Dict[str, datetime] = field(default_factory=dict)
    
    def record_success(self, selector_type: str, selector: str):
        """Record a successful selector use."""
        setattr(self, selector_type, selector)
        self.success_count[selector] = self.success_count.get(selector, 0) + 1
        self.last_success[selector] = datetime.now()
        
        # Add to alternatives if not already there
        if selector_type not in self.alternatives:
            self.alternatives[selector_type] = []
        if selector not in self.alternatives[selector_type]:
            self.alternatives[selector_type].append(selector)
    
    def get_alternatives(self, selector_type: str) -> List[str]:
        """Get alternative selectors for a given type."""
        return self.alternatives.get(selector_type, [])


@dataclass
class StrategyPerformance:
    """
    Performance tracking for a specific strategy on a site.
    
    Enables learning which strategies work best for each site.
    """
    strategy_name: str
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    total_jobs_extracted: int = 0
    total_time_seconds: float = 0.0
    last_attempt: Optional[datetime] = None
    last_success: Optional[datetime] = None
    
    def record_attempt(self, success: bool, jobs_extracted: int = 0, duration: float = 0.0):
        """Record a strategy execution attempt."""
        self.attempts += 1
        self.last_attempt = datetime.now()
        self.total_time_seconds += duration
        
        if success:
            self.successes += 1
            self.last_success = datetime.now()
            self.total_jobs_extracted += jobs_extracted
        else:
            self.failures += 1
    
    def success_rate(self) -> float:
        """Calculate success rate for this strategy."""
        if self.attempts == 0:
            return 0.5  # Prior probability for untried strategies
        return self.successes / self.attempts
    
    def average_yield(self) -> float:
        """Average jobs extracted per attempt."""
        if self.attempts == 0:
            return 0.0
        return self.total_jobs_extracted / self.attempts
    
    def efficiency(self) -> float:
        """Jobs per minute for this strategy."""
        if self.total_time_seconds == 0:
            return 0.0
        return (self.total_jobs_extracted / self.total_time_seconds) * 60


@dataclass
class TargetSiteModel:
    """
    Internal representation of what the agent knows about a target site.
    
    This is the core of the World Model - maintaining beliefs about
    a specific website's characteristics, threat level, and optimal
    extraction strategies.
    """
    
    # Identity
    domain: str
    first_seen: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    
    # Detected Capabilities
    capabilities: Set[SiteCapability] = field(default_factory=set)
    
    # Threat Assessment
    threat_level: ThreatLevel = ThreatLevel.NONE
    consecutive_429_count: int = 0
    consecutive_403_count: int = 0
    total_blocks: int = 0
    
    # Rate Limit Awareness
    last_request_time: Optional[datetime] = None
    recommended_delay_seconds: float = 3.0
    observed_rate_limit: Optional[int] = None  # Requests per minute if detected
    
    # Strategy Performance
    strategy_performance: Dict[str, StrategyPerformance] = field(default_factory=dict)
    
    # DOM Structure Memory
    selectors: SelectorMemory = field(default_factory=SelectorMemory)
    
    # Sitemap Information
    sitemap_url: Optional[str] = None
    sitemap_type: Optional[str] = None  # 'xml' or 'html'
    last_sitemap_check: Optional[datetime] = None
    
    # Known Endpoints
    known_api_endpoints: List[str] = field(default_factory=list)
    
    # ========================
    # Capability Detection
    # ========================
    
    def add_capability(self, capability: SiteCapability):
        """Add a detected capability."""
        self.capabilities.add(capability)
    
    def has_capability(self, capability: SiteCapability) -> bool:
        """Check if site has a capability."""
        return capability in self.capabilities
    
    def detect_sitemap(self, sitemap_url: str, sitemap_type: str):
        """Record sitemap detection."""
        self.sitemap_url = sitemap_url
        self.sitemap_type = sitemap_type
        self.last_sitemap_check = datetime.now()
        
        if sitemap_type == 'xml':
            self.add_capability(SiteCapability.SITEMAP_XML)
        else:
            self.add_capability(SiteCapability.SITEMAP_HTML)
        self.add_capability(SiteCapability.SITEMAP_AVAILABLE)
    
    # ========================
    # Threat Level Management
    # ========================
    
    def update_threat_level(self, status_code: int):
        """
        Update threat level based on HTTP response.
        
        Implements a state machine for threat assessment:
        - Successful responses decrease threat
        - 429s increase threat progressively
        - 403s immediately set BLOCKED
        """
        self.last_accessed = datetime.now()
        
        if status_code == 429:
            self.consecutive_429_count += 1
            self.consecutive_403_count = 0
            
            if self.consecutive_429_count >= 3:
                self.threat_level = ThreatLevel.HIGH
                self.recommended_delay_seconds = 30.0
            elif self.consecutive_429_count >= 1:
                self.threat_level = ThreatLevel.MEDIUM
                self.recommended_delay_seconds = 15.0
                
        elif status_code == 403:
            self.consecutive_403_count += 1
            self.total_blocks += 1
            self.threat_level = ThreatLevel.BLOCKED
            self.recommended_delay_seconds = 60.0
            
        elif 200 <= status_code < 300:
            # Successful response - gradually decrease threat
            self.consecutive_429_count = 0
            self.consecutive_403_count = 0
            
            if self.threat_level == ThreatLevel.HIGH:
                self.threat_level = ThreatLevel.MEDIUM
                self.recommended_delay_seconds = 10.0
            elif self.threat_level == ThreatLevel.MEDIUM:
                self.threat_level = ThreatLevel.LOW
                self.recommended_delay_seconds = 5.0
            elif self.threat_level != ThreatLevel.BLOCKED:
                self.threat_level = ThreatLevel.NONE
                self.recommended_delay_seconds = 3.0
    
    def is_safe_to_request(self) -> bool:
        """Check if it's currently safe to make a request."""
        return self.threat_level != ThreatLevel.BLOCKED
    
    def get_recommended_delay(self) -> float:
        """Get recommended delay before next request."""
        return max(self.recommended_delay_seconds, self.threat_level.get_recommended_delay())
    
    # ========================
    # Strategy Performance
    # ========================
    
    def get_strategy_performance(self, strategy_name: str) -> StrategyPerformance:
        """Get or create performance tracker for a strategy."""
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = StrategyPerformance(strategy_name)
        return self.strategy_performance[strategy_name]
    
    def record_strategy_attempt(
        self, 
        strategy_name: str, 
        success: bool, 
        jobs_extracted: int = 0,
        duration: float = 0.0
    ):
        """Record a strategy execution attempt."""
        perf = self.get_strategy_performance(strategy_name)
        perf.record_attempt(success, jobs_extracted, duration)
    
    def get_best_strategy(self) -> Optional[str]:
        """Get the strategy with highest success rate for this site."""
        if not self.strategy_performance:
            return None
        
        # Sort by success rate, then by efficiency
        ranked = sorted(
            self.strategy_performance.items(),
            key=lambda x: (x[1].success_rate(), x[1].efficiency()),
            reverse=True
        )
        
        return ranked[0][0] if ranked else None
    
    def get_strategy_success_rate(self, strategy_name: str) -> float:
        """Get success rate for a specific strategy."""
        if strategy_name not in self.strategy_performance:
            return 0.5  # Prior probability
        return self.strategy_performance[strategy_name].success_rate()
    
    # ========================
    # Serialization
    # ========================
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for persistence."""
        return {
            'domain': self.domain,
            'first_seen': self.first_seen.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'capabilities': [c.value for c in self.capabilities],
            'threat_level': self.threat_level.value,
            'total_blocks': self.total_blocks,
            'recommended_delay': self.recommended_delay_seconds,
            'sitemap_url': self.sitemap_url,
            'sitemap_type': self.sitemap_type,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TargetSiteModel':
        """Deserialize from dictionary."""
        site = cls(domain=data['domain'])
        site.first_seen = datetime.fromisoformat(data.get('first_seen', datetime.now().isoformat()))
        site.last_accessed = datetime.fromisoformat(data.get('last_accessed', datetime.now().isoformat()))
        site.capabilities = {SiteCapability(c) for c in data.get('capabilities', [])}
        site.threat_level = ThreatLevel(data.get('threat_level', 0))
        site.total_blocks = data.get('total_blocks', 0)
        site.recommended_delay_seconds = data.get('recommended_delay', 3.0)
        site.sitemap_url = data.get('sitemap_url')
        site.sitemap_type = data.get('sitemap_type')
        return site


@dataclass
class WorldModel:
    """
    Global world state maintained by the agent.
    
    This is the agent's "memory" of everything it knows:
    - All encountered sites and their states
    - URLs already visited
    - Extracted jobs
    - Global threat awareness
    
    Supports persistence to survive across sessions.
    """
    
    # Site Knowledge Base
    sites: Dict[str, TargetSiteModel] = field(default_factory=dict)
    
    # URL Tracking
    seen_urls: Set[str] = field(default_factory=set)
    failed_urls: Set[str] = field(default_factory=set)
    
    # Extracted Results
    extracted_jobs: List[Dict[str, Any]] = field(default_factory=list)
    seen_apply_links: Set[str] = field(default_factory=set)
    
    # Global State
    global_rate_limit_active: bool = False
    session_start_time: Optional[datetime] = None
    total_requests: int = 0
    
    # Persistence Path
    persistence_path: Optional[str] = None
    
    # ========================
    # Site Management
    # ========================
    
    def get_or_create_site(self, domain: str) -> TargetSiteModel:
        """
        Get existing site model or create new one.
        
        Args:
            domain: Domain name (e.g., 'example.com')
            
        Returns:
            TargetSiteModel for the domain
        """
        # Normalize domain
        domain = domain.lower().replace('www.', '')
        
        if domain not in self.sites:
            self.sites[domain] = TargetSiteModel(domain=domain)
        
        return self.sites[domain]
    
    def get_site(self, domain: str) -> Optional[TargetSiteModel]:
        """Get site model if it exists."""
        domain = domain.lower().replace('www.', '')
        return self.sites.get(domain)
    
    def extract_domain(self, url: str) -> str:
        """Extract domain from a URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower().replace('www.', '')
    
    # ========================
    # URL Tracking
    # ========================
    
    def mark_url_visited(self, url: str):
        """Mark a URL as visited."""
        self.seen_urls.add(url)
    
    def mark_url_failed(self, url: str):
        """Mark a URL as failed."""
        self.failed_urls.add(url)
        self.seen_urls.add(url)
    
    def is_url_seen(self, url: str) -> bool:
        """Check if URL has been visited."""
        return url in self.seen_urls
    
    def is_apply_link_seen(self, link: str) -> bool:
        """Check if an apply link has been seen (duplicate detection)."""
        return link.strip() in self.seen_apply_links
    
    def add_apply_link(self, link: str):
        """Add apply link to seen set."""
        self.seen_apply_links.add(link.strip())
    
    # ========================
    # Result Management
    # ========================
    
    def add_extracted_job(self, job_data: Dict[str, Any]):
        """Add an extracted job to results."""
        self.extracted_jobs.append(job_data)
        
        # Track the apply link for duplicate detection
        if 'link' in job_data:
            self.add_apply_link(job_data['link'])
        elif 'Apply_Link' in job_data:
            self.add_apply_link(job_data['Apply_Link'])
    
    def get_unique_job_count(self) -> int:
        """Get count of unique extracted jobs."""
        return len(self.extracted_jobs)
    
    # ========================
    # Global State
    # ========================
    
    def start_session(self):
        """Start a new scraping session."""
        self.session_start_time = datetime.now()
        self.total_requests = 0
    
    def record_request(self, domain: str, status_code: int):
        """Record a request and update site threat level."""
        self.total_requests += 1
        site = self.get_or_create_site(domain)
        site.update_threat_level(status_code)
        site.last_request_time = datetime.now()
    
    def get_total_threat_level(self) -> ThreatLevel:
        """Get overall threat level across all sites."""
        if not self.sites:
            return ThreatLevel.NONE
        
        max_threat = max(site.threat_level for site in self.sites.values())
        return max_threat
    
    # ========================
    # Shared History Integration
    # ========================
    
    def load_shared_history(self, history_path: str) -> int:
        """
        Load shared history file (seen_apply_link.txt).
        
        Args:
            history_path: Path to the shared history file
            
        Returns:
            Number of links loaded
        """
        loaded = 0
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        link = line.strip()
                        if link:
                            self.seen_apply_links.add(link)
                            loaded += 1
            except Exception as e:
                print(f"Warning: Could not load shared history: {e}")
        return loaded
    
    def save_to_shared_history(self, history_path: str, new_links: List[str]):
        """
        Append new links to shared history file.
        
        Args:
            history_path: Path to the shared history file
            new_links: List of new apply links to save
        """
        try:
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            with open(history_path, 'a', encoding='utf-8') as f:
                for link in new_links:
                    f.write(link.strip() + '\n')
        except Exception as e:
            print(f"Warning: Could not save to shared history: {e}")
    
    # ========================
    # Persistence
    # ========================
    
    def save(self, path: Optional[str] = None):
        """
        Save world model to disk for persistence across sessions.
        
        Args:
            path: File path for saving (uses self.persistence_path if not provided)
        """
        save_path = path or self.persistence_path
        if not save_path:
            return
        
        data = {
            'sites': {domain: site.to_dict() for domain, site in self.sites.items()},
            'seen_urls': list(self.seen_urls),
            'seen_apply_links': list(self.seen_apply_links),
            'total_requests': self.total_requests,
        }
        
        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save world model: {e}")
    
    def load(self, path: str) -> bool:
        """
        Load world model from disk.
        
        Args:
            path: File path to load from
            
        Returns:
            True if successfully loaded
        """
        if not os.path.exists(path):
            return False
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Restore sites
            for domain, site_data in data.get('sites', {}).items():
                self.sites[domain] = TargetSiteModel.from_dict(site_data)
            
            # Restore URL sets
            self.seen_urls = set(data.get('seen_urls', []))
            self.seen_apply_links = set(data.get('seen_apply_links', []))
            self.total_requests = data.get('total_requests', 0)
            
            self.persistence_path = path
            return True
            
        except Exception as e:
            print(f"Warning: Could not load world model: {e}")
            return False
    
    # ========================
    # Summary
    # ========================
    
    def get_summary(self) -> Dict[str, Any]:
        """Generate a summary of world state."""
        blocked_sites = [d for d, s in self.sites.items() if s.threat_level == ThreatLevel.BLOCKED]
        
        return {
            'total_sites': len(self.sites),
            'blocked_sites': blocked_sites,
            'urls_visited': len(self.seen_urls),
            'urls_failed': len(self.failed_urls),
            'jobs_extracted': len(self.extracted_jobs),
            'apply_links_seen': len(self.seen_apply_links),
            'total_requests': self.total_requests,
            'overall_threat': self.get_total_threat_level().name,
        }
    
    def __str__(self) -> str:
        summary = self.get_summary()
        return (
            f"WorldModel: {summary['total_sites']} sites, "
            f"{summary['urls_visited']} URLs, "
            f"{summary['jobs_extracted']} jobs | "
            f"Threat: {summary['overall_threat']}"
        )
