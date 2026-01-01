"""
Recovery Engine Module
======================
Failure analysis and intelligent recovery for the CareerBoard agent.

This is the "thinking" module - what the agent does when things go wrong.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
import random
import time

from .world_model import WorldModel, ThreatLevel
from .goal import ScrapingGoal, GoalStatus
from .planner import StrategyPlanner, Plan, Strategy, StrategyType, StrategyConfig


class FailureType(Enum):
    """Classification of failure types."""
    NETWORK_TIMEOUT = "network_timeout"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    CAPTCHA_DETECTED = "captcha_detected"
    LAYOUT_CHANGED = "layout_changed"
    NO_CONTENT_FOUND = "no_content_found"
    AUTHENTICATION_REQUIRED = "authentication_required"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"


@dataclass
class RecoveryDecision:
    """The agent's decision after analyzing a failure."""
    should_retry: bool
    new_plan: Optional[Plan] = None
    wait_seconds: float = 0.0
    rotate_identity: bool = False
    switch_strategy: bool = False
    abort_reason: Optional[str] = None
    log_message: str = ""
    
    def __str__(self) -> str:
        if not self.should_retry:
            return f"ABORT: {self.abort_reason}"
        actions = []
        if self.wait_seconds > 0:
            actions.append(f"wait {self.wait_seconds:.1f}s")
        if self.rotate_identity:
            actions.append("rotate identity")
        if self.switch_strategy:
            actions.append("switch strategy")
        return f"RECOVER: {', '.join(actions)}"


class RecoveryEngine:
    """
    The 'Thinking' module: Analyzes failures and decides on recovery actions.
    
    Implements goal-driven recovery considering:
    1. Type of failure
    2. Current goal progress
    3. World model state
    4. Available alternatives
    """
    
    MAX_RETRIES_PER_STRATEGY = 3
    MAX_CONSECUTIVE_FAILURES = 10
    
    def __init__(self, goal: ScrapingGoal, world_model: WorldModel, planner: StrategyPlanner):
        self.goal = goal
        self.world_model = world_model
        self.planner = planner
        self._consecutive_failures = 0
        self._strategy_retry_counts: Dict[str, int] = {}
        self._failure_history: List[Dict[str, Any]] = []
    
    def analyze_and_decide(
        self,
        failure_type: FailureType,
        current_plan: Plan,
        error_context: Dict[str, Any]
    ) -> RecoveryDecision:
        """
        Main recovery logic - analyze failure and decide next action.
        
        PSEUDOCODE:
        1. Classify failure severity
        2. Check if goal is still achievable
        3. Evaluate current strategy viability
        4. Decide: Retry, Switch Strategy, or Abort
        """
        self._consecutive_failures += 1
        current_strategy = current_plan.current_strategy()
        strategy_name = current_strategy.name.value if current_strategy else "unknown"
        
        # Record failure
        self._strategy_retry_counts[strategy_name] = \
            self._strategy_retry_counts.get(strategy_name, 0) + 1
        
        self._failure_history.append({
            'type': failure_type.value,
            'strategy': strategy_name,
            'context': error_context,
            'timestamp': time.time()
        })
        
        # === STEP 1: Should we abort entirely? ===
        abort_decision = self._check_abort_conditions(failure_type)
        if abort_decision:
            return abort_decision
        
        # === STEP 2: Handle specific failure types ===
        specific_decision = self._handle_specific_failure(failure_type, current_plan, error_context)
        if specific_decision:
            return specific_decision
        
        # === STEP 3: Should we switch strategies? ===
        if self._strategy_retry_counts.get(strategy_name, 0) >= self.MAX_RETRIES_PER_STRATEGY:
            return self._switch_strategy_decision(current_plan, strategy_name)
        
        # === STEP 4: Default retry with backoff ===
        return self._default_retry_decision()
    
    def _check_abort_conditions(self, failure_type: FailureType) -> Optional[RecoveryDecision]:
        """Check if we should abort the entire operation."""
        
        if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            return RecoveryDecision(
                should_retry=False,
                abort_reason=f"Max consecutive failures ({self.MAX_CONSECUTIVE_FAILURES}) reached",
                log_message="[ABORT] Too many consecutive failures. Stopping to prevent IP ban."
            )
        
        if self.goal.get_status() == GoalStatus.FAILED:
            return RecoveryDecision(
                should_retry=False,
                abort_reason="Goal marked as failed (error rate exceeded)",
                log_message="[ABORT] Error rate exceeded acceptable threshold."
            )
        
        if self.goal.is_resource_exhausted():
            if self.goal.valid_jobs_found > 0:
                return RecoveryDecision(
                    should_retry=False,
                    abort_reason=f"Resources exhausted. Found {self.goal.valid_jobs_found} jobs.",
                    log_message=f"[COMPLETE] Time/request limit reached. Partial success: {self.goal.valid_jobs_found} jobs."
                )
            else:
                return RecoveryDecision(
                    should_retry=False,
                    abort_reason="Resources exhausted with no results",
                    log_message="[ABORT] Time/request limit reached with no results."
                )
        
        return None
    
    def _handle_specific_failure(
        self,
        failure_type: FailureType,
        current_plan: Plan,
        error_context: Dict[str, Any]
    ) -> Optional[RecoveryDecision]:
        """Handle specific failure types with targeted recovery."""
        
        if failure_type == FailureType.RATE_LIMITED:
            wait_time = min(300, 30 * (2 ** min(self._consecutive_failures, 4)))
            return RecoveryDecision(
                should_retry=True,
                wait_seconds=wait_time,
                rotate_identity=True,
                log_message=f"[RATE_LIMIT] Detected 429. Waiting {wait_time}s, rotating identity."
            )
        
        elif failure_type == FailureType.BLOCKED:
            if self._consecutive_failures < 3:
                wait_time = 120 + random.uniform(0, 30)
                return RecoveryDecision(
                    should_retry=True,
                    wait_seconds=wait_time,
                    rotate_identity=True,
                    log_message=f"[BLOCKED] IP/Session blocked. Waiting {wait_time:.0f}s, rotating identity."
                )
            else:
                new_plan = self.planner.replan_after_failure(current_plan, "blocked")
                return RecoveryDecision(
                    should_retry=new_plan.has_more(),
                    new_plan=new_plan,
                    switch_strategy=True,
                    log_message="[BLOCKED] Persistently blocked. Switching to fallback strategies."
                )
        
        elif failure_type == FailureType.CAPTCHA_DETECTED:
            current_plan.advance()
            return RecoveryDecision(
                should_retry=current_plan.has_more(),
                switch_strategy=True,
                log_message="[CAPTCHA] Detected. Cannot solve automatically. Skipping to next strategy."
            )
        
        elif failure_type == FailureType.LAYOUT_CHANGED:
            return RecoveryDecision(
                should_retry=True,
                wait_seconds=5,
                log_message="[LAYOUT] Structure changed. Attempting adaptive extraction."
            )
        
        elif failure_type == FailureType.AUTHENTICATION_REQUIRED:
            current_plan.advance()
            return RecoveryDecision(
                should_retry=current_plan.has_more(),
                switch_strategy=True,
                log_message="[AUTH] Login required. Skipping protected resource."
            )
        
        elif failure_type == FailureType.SERVER_ERROR:
            wait_time = 30 * self._consecutive_failures
            return RecoveryDecision(
                should_retry=True,
                wait_seconds=min(wait_time, 120),
                log_message=f"[SERVER] 5xx error. Waiting {wait_time}s for server recovery."
            )
        
        elif failure_type == FailureType.NETWORK_TIMEOUT:
            if self._consecutive_failures < 3:
                return RecoveryDecision(
                    should_retry=True,
                    wait_seconds=10 * self._consecutive_failures,
                    log_message=f"[TIMEOUT] Network timeout. Retrying with extended timeout."
                )
            else:
                return RecoveryDecision(
                    should_retry=False,
                    abort_reason="Persistent network timeout",
                    log_message="[ABORT] Network unreliable. Cannot continue."
                )
        
        return None
    
    def _switch_strategy_decision(self, current_plan: Plan, strategy_name: str) -> RecoveryDecision:
        """Decide to switch to next strategy."""
        if current_plan.has_more():
            current_plan.advance()
            self._consecutive_failures = 0
            return RecoveryDecision(
                should_retry=True,
                switch_strategy=True,
                log_message=f"[REPLAN] Strategy '{strategy_name}' exhausted. Switching to next."
            )
        else:
            new_plan = self.planner.replan_after_failure(current_plan, "exhausted")
            if new_plan.has_more():
                return RecoveryDecision(
                    should_retry=True,
                    new_plan=new_plan,
                    switch_strategy=True,
                    log_message="[REPLAN] All strategies failed. Generated fallback plan."
                )
            else:
                return RecoveryDecision(
                    should_retry=False,
                    abort_reason="All strategies exhausted",
                    log_message="[ABORT] No viable strategies remaining."
                )
    
    def _default_retry_decision(self) -> RecoveryDecision:
        """Default retry with exponential backoff."""
        wait_time = self._calculate_backoff()
        return RecoveryDecision(
            should_retry=True,
            wait_seconds=wait_time,
            rotate_identity=self._consecutive_failures >= 2,
            log_message=f"[RETRY] Waiting {wait_time:.1f}s. Attempt {self._consecutive_failures + 1}"
        )
    
    def _calculate_backoff(self) -> float:
        """Exponential backoff with jitter."""
        base_delay = 5.0
        max_delay = 60.0
        delay = min(max_delay, base_delay * (2 ** min(self._consecutive_failures, 5)))
        jitter = random.uniform(0, delay * 0.3)
        return delay + jitter
    
    def reset_on_success(self):
        """Reset failure tracking on successful action."""
        self._consecutive_failures = 0
    
    def get_failure_summary(self) -> Dict[str, Any]:
        """Get summary of failures for analysis."""
        failure_counts = {}
        for f in self._failure_history:
            ft = f['type']
            failure_counts[ft] = failure_counts.get(ft, 0) + 1
        
        return {
            'total_failures': len(self._failure_history),
            'consecutive_failures': self._consecutive_failures,
            'by_type': failure_counts,
            'by_strategy': dict(self._strategy_retry_counts)
        }


def classify_error(error: Exception, response_code: Optional[int] = None) -> FailureType:
    """Classify an exception into a FailureType."""
    error_str = str(error).lower()
    
    if response_code:
        if response_code == 429:
            return FailureType.RATE_LIMITED
        elif response_code == 403:
            return FailureType.BLOCKED
        elif response_code >= 500:
            return FailureType.SERVER_ERROR
    
    if "429" in error_str or "rate limit" in error_str:
        return FailureType.RATE_LIMITED
    elif "403" in error_str or "forbidden" in error_str:
        return FailureType.BLOCKED
    elif "captcha" in error_str or "challenge" in error_str:
        return FailureType.CAPTCHA_DETECTED
    elif "timeout" in error_str:
        return FailureType.NETWORK_TIMEOUT
    elif "login" in error_str or "auth" in error_str or "sign in" in error_str:
        return FailureType.AUTHENTICATION_REQUIRED
    elif "not found" in error_str or "element" in error_str or "selector" in error_str:
        return FailureType.LAYOUT_CHANGED
    elif "empty" in error_str or "no content" in error_str:
        return FailureType.NO_CONTENT_FOUND
    else:
        return FailureType.UNKNOWN
