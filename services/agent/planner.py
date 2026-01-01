"""
Strategy Planner Module
=======================
Goal-driven strategy selection and planning for the CareerBoard agent.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum
from urllib.parse import urlparse
from datetime import datetime

from .world_model import WorldModel, ThreatLevel, SiteCapability, TargetSiteModel
from .goal import ScrapingGoal


class StrategyType(Enum):
    """Available extraction strategies."""
    SITEMAP_CRAWL = "sitemap_crawl"
    AUTO_DISCOVERY = "auto_discovery"
    DIRECT_LISTING = "direct_listing"
    API_EXTRACTION = "api_extraction"
    RSS_FEED = "rss_feed"
    GOOGLE_CACHE = "google_cache"
    WAYBACK_MACHINE = "wayback_machine"


@dataclass
class StrategyConfig:
    """Configuration parameters for a strategy."""
    max_pages: int = 50
    max_urls_per_run: int = 100
    timeout_seconds: int = 30
    retry_count: int = 3
    delay_between_requests: float = 3.0


@dataclass
class Strategy:
    """A planned action to achieve extraction goals."""
    name: StrategyType
    target_url: str
    priority: int
    estimated_yield: int
    risk_level: float
    config: StrategyConfig = field(default_factory=StrategyConfig)
    attempt_count: int = 0
    last_attempt_success: Optional[bool] = None
    jobs_extracted: int = 0
    
    def effectiveness_score(self) -> float:
        """Calculate strategy effectiveness score."""
        if self.priority == 0:
            self.priority = 1
        return (self.estimated_yield * (1 - self.risk_level)) / self.priority
    
    def increment_attempt(self):
        self.attempt_count += 1
    
    def record_result(self, success: bool, jobs: int = 0):
        self.last_attempt_success = success
        self.jobs_extracted += jobs


@dataclass
class Plan:
    """Ordered list of strategies to achieve the goal."""
    strategies: List[Strategy]
    current_index: int = 0
    created_at: str = ""
    goal_target: int = 0
    
    def current_strategy(self) -> Optional[Strategy]:
        if self.current_index < len(self.strategies):
            return self.strategies[self.current_index]
        return None
    
    def advance(self):
        self.current_index += 1
    
    def has_more(self) -> bool:
        return self.current_index < len(self.strategies)
    
    def remaining_count(self) -> int:
        return max(0, len(self.strategies) - self.current_index)
    
    def get_remaining(self) -> List[Strategy]:
        return self.strategies[self.current_index:]
    
    def insert_priority_strategy(self, strategy: Strategy):
        self.strategies.insert(self.current_index, strategy)
    
    def total_expected_yield(self) -> int:
        return sum(s.estimated_yield for s in self.get_remaining())


class StrategyPlanner:
    """Goal-Based Planning: Selects and orders strategies."""
    
    DEFAULT_SCORES = {
        StrategyType.SITEMAP_CRAWL: (30, 0.1),
        StrategyType.AUTO_DISCOVERY: (20, 0.3),
        StrategyType.DIRECT_LISTING: (10, 0.2),
        StrategyType.API_EXTRACTION: (50, 0.15),
        StrategyType.RSS_FEED: (15, 0.05),
        StrategyType.GOOGLE_CACHE: (5, 0.4),
        StrategyType.WAYBACK_MACHINE: (3, 0.3),
    }
    
    def __init__(self, goal: ScrapingGoal, world_model: WorldModel):
        self.goal = goal
        self.world_model = world_model
    
    def generate_plan(self, target_url: str) -> Plan:
        """Generate an ordered plan of strategies."""
        domain = self._extract_domain(target_url)
        site = self.world_model.get_or_create_site(domain)
        candidates = []
        
        # Sitemap strategy
        sitemap_strategy = self._create_sitemap_strategy(target_url, site)
        if sitemap_strategy:
            candidates.append(sitemap_strategy)
        
        # Auto-discovery strategy
        auto_strategy = self._create_auto_discovery_strategy(target_url, site)
        candidates.append(auto_strategy)
        
        # API if available
        if site.has_capability(SiteCapability.API_AVAILABLE):
            api_strategy = self._create_api_strategy(target_url, site)
            if api_strategy:
                candidates.append(api_strategy)
        
        # Google Cache fallback if blocked
        if site.threat_level == ThreatLevel.BLOCKED:
            cache_strategy = self._create_google_cache_strategy(target_url, site)
            candidates.append(cache_strategy)
        
        # Sort by effectiveness
        candidates.sort(key=lambda s: s.effectiveness_score(), reverse=True)
        for i, strategy in enumerate(candidates):
            strategy.priority = i + 1
        
        return Plan(
            strategies=candidates,
            created_at=datetime.now().isoformat(),
            goal_target=self.goal.target_valid_jobs
        )
    
    def replan_after_failure(self, current_plan: Plan, failure_reason: str) -> Plan:
        """Reactive replanning after a strategy fails."""
        remaining = current_plan.get_remaining()
        if not remaining:
            return self._generate_fallback_plan(current_plan)
        
        failure_lower = failure_reason.lower()
        
        if "429" in failure_lower or "rate limit" in failure_lower:
            for strategy in remaining:
                strategy.risk_level = min(1.0, strategy.risk_level + 0.2)
                strategy.config.delay_between_requests *= 2
        
        elif "403" in failure_lower or "blocked" in failure_lower:
            target_url = remaining[0].target_url if remaining else ""
            site = self.world_model.get_or_create_site(self._extract_domain(target_url))
            fallback = self._create_google_cache_strategy(target_url, site)
            remaining.append(fallback)
        
        remaining.sort(key=lambda s: s.effectiveness_score(), reverse=True)
        return Plan(strategies=remaining, created_at=datetime.now().isoformat())
    
    def _create_sitemap_strategy(self, target_url: str, site: TargetSiteModel) -> Strategy:
        domain = self._extract_domain(target_url)
        sitemap_url = site.sitemap_url or f"https://{domain}/sitemap.xml"
        perf = site.get_strategy_performance(StrategyType.SITEMAP_CRAWL.value)
        
        if perf.attempts > 0:
            expected_yield = int(perf.average_yield()) or 30
            risk = 1.0 - perf.success_rate()
        else:
            expected_yield, risk = self.DEFAULT_SCORES[StrategyType.SITEMAP_CRAWL]
        
        risk = min(1.0, risk + (site.threat_level.value * 0.1))
        
        return Strategy(
            name=StrategyType.SITEMAP_CRAWL,
            target_url=sitemap_url,
            priority=1,
            estimated_yield=expected_yield,
            risk_level=risk,
            config=StrategyConfig(delay_between_requests=site.get_recommended_delay())
        )
    
    def _create_auto_discovery_strategy(self, target_url: str, site: TargetSiteModel) -> Strategy:
        perf = site.get_strategy_performance(StrategyType.AUTO_DISCOVERY.value)
        
        if perf.attempts > 0:
            expected_yield = int(perf.average_yield()) or 20
            risk = 1.0 - perf.success_rate()
        else:
            expected_yield, risk = self.DEFAULT_SCORES[StrategyType.AUTO_DISCOVERY]
        
        if site.has_capability(SiteCapability.CLOUDFLARE_PROTECTED):
            risk = min(1.0, risk + 0.3)
        risk = min(1.0, risk + (site.threat_level.value * 0.15))
        
        return Strategy(
            name=StrategyType.AUTO_DISCOVERY,
            target_url=target_url,
            priority=2,
            estimated_yield=expected_yield,
            risk_level=risk,
            config=StrategyConfig(max_pages=30, delay_between_requests=site.get_recommended_delay())
        )
    
    def _create_api_strategy(self, target_url: str, site: TargetSiteModel) -> Optional[Strategy]:
        if not site.known_api_endpoints:
            return None
        api_url = site.known_api_endpoints[0]
        expected_yield, risk = self.DEFAULT_SCORES[StrategyType.API_EXTRACTION]
        return Strategy(
            name=StrategyType.API_EXTRACTION,
            target_url=api_url,
            priority=1,
            estimated_yield=expected_yield,
            risk_level=risk,
            config=StrategyConfig(delay_between_requests=1.0)
        )
    
    def _create_google_cache_strategy(self, target_url: str, site: TargetSiteModel) -> Strategy:
        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{target_url}"
        expected_yield, risk = self.DEFAULT_SCORES[StrategyType.GOOGLE_CACHE]
        return Strategy(
            name=StrategyType.GOOGLE_CACHE,
            target_url=cache_url,
            priority=10,
            estimated_yield=expected_yield,
            risk_level=risk,
            config=StrategyConfig(max_urls_per_run=10)
        )
    
    def _generate_fallback_plan(self, failed_plan: Plan) -> Plan:
        if not failed_plan.strategies:
            return Plan(strategies=[])
        original_url = failed_plan.strategies[0].target_url
        domain = self._extract_domain(original_url)
        site = self.world_model.get_or_create_site(domain)
        
        fallbacks = [
            self._create_google_cache_strategy(original_url, site),
            Strategy(
                name=StrategyType.WAYBACK_MACHINE,
                target_url=f"https://web.archive.org/web/{original_url}",
                priority=11,
                estimated_yield=3,
                risk_level=0.3,
                config=StrategyConfig()
            )
        ]
        return Plan(strategies=fallbacks, created_at=datetime.now().isoformat())
    
    def _extract_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc.lower().replace('www.', '')
