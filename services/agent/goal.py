"""
Goal Representation Module
==========================
Explicit goal formulation for the CareerBoard agent.

This module implements goal-based reasoning by:
1. Defining explicit, measurable objectives
2. Tracking progress towards those objectives
3. Determining goal achievement/failure status

Reference: Russell & Norvig (2021) - "Artificial Intelligence: A Modern Approach"
           Chapter 2: Intelligent Agents - Goal-Based Agents
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
import time


class GoalStatus(Enum):
    """
    Possible states of goal achievement.
    
    State Transitions:
        PENDING -> IN_PROGRESS (on first successful extraction)
        IN_PROGRESS -> ACHIEVED (when target reached)
        IN_PROGRESS -> PARTIALLY_ACHIEVED (on timeout with some results)
        IN_PROGRESS -> FAILED (on error threshold breach)
        PENDING -> FAILED (on immediate failure)
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    FAILED = "failed"
    PARTIALLY_ACHIEVED = "partially_achieved"


class GoalPriority(Enum):
    """Priority levels for multi-goal scenarios."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class QualityConstraints:
    """
    Quality thresholds that define acceptable performance.
    
    These constraints implement the Performance Measure (P) 
    from the PEAS framework.
    """
    min_confidence_score: float = 0.30  # Minimum link confidence score
    max_error_rate: float = 0.15        # Maximum acceptable error rate
    min_precision: float = 0.85         # Minimum extraction precision
    max_duplicate_rate: float = 0.30    # Maximum duplicate rate before stopping


@dataclass
class ResourceLimits:
    """
    Resource constraints for agent execution.
    
    Prevents runaway execution and implements
    responsible resource usage.
    """
    max_execution_time_seconds: int = 3600      # 1 hour default
    max_requests_per_session: int = 500         # Rate limit protection
    max_retries_per_url: int = 3                # Per-URL retry limit
    max_consecutive_failures: int = 10          # Failure tolerance


@dataclass
class ScrapingGoal:
    """
    Explicit goal representation for the CareerBoard agent.
    
    This class transforms the implicit "scrape until done" script behavior
    into an explicit, measurable goal that the agent actively pursues.
    
    Attributes:
        target_valid_jobs: Primary objective - number of jobs to extract
        target_domains: Optional list of specific domains to target
        date_range: Tuple of (start_date, end_date) for filtering
        quality: Quality constraints (precision, error rate)
        resources: Resource limits (time, requests)
        
    Example:
        goal = ScrapingGoal(
            target_valid_jobs=50,
            quality=QualityConstraints(min_confidence_score=0.5),
            resources=ResourceLimits(max_execution_time_seconds=1800)
        )
    """
    
    # Primary Objectives
    target_valid_jobs: int = 50
    target_domains: Optional[List[str]] = None
    date_range: Optional[tuple] = None  # (start_date_str, end_date_str)
    
    # Constraints
    quality: QualityConstraints = field(default_factory=QualityConstraints)
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    priority: GoalPriority = GoalPriority.MEDIUM
    
    # Progress Tracking (Mutable State)
    valid_jobs_found: int = 0
    total_attempts: int = 0
    errors_encountered: int = 0
    duplicates_found: int = 0
    requests_made: int = 0
    
    # Timing
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    # Results Storage
    extracted_jobs: List[Dict[str, Any]] = field(default_factory=list)
    failed_urls: List[str] = field(default_factory=list)
    
    # ========================
    # Goal Status Evaluation
    # ========================
    
    def is_achieved(self) -> bool:
        """
        Check if the primary goal has been achieved.
        
        Returns:
            True if we've found the target number of valid jobs
        """
        return self.valid_jobs_found >= self.target_valid_jobs
    
    def is_failed(self) -> bool:
        """
        Check if the goal has failed due to quality constraint violations.
        
        Failure conditions:
        1. Error rate exceeds maximum allowed
        2. Consecutive failures exceed threshold (handled by RecoveryEngine)
        
        Returns:
            True if error rate threshold has been breached
        """
        if self.total_attempts == 0:
            return False
        error_rate = self.errors_encountered / self.total_attempts
        return error_rate > self.quality.max_error_rate
    
    def is_resource_exhausted(self) -> bool:
        """
        Check if resource limits have been reached.
        
        Returns:
            True if time or request limits exceeded
        """
        # Time limit check
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            if elapsed > self.resources.max_execution_time_seconds:
                return True
        
        # Request limit check
        if self.requests_made >= self.resources.max_requests_per_session:
            return True
        
        return False
    
    def get_status(self) -> GoalStatus:
        """
        Determine the current status of goal achievement.
        
        Returns:
            Current GoalStatus enum value
        """
        if self.is_achieved():
            return GoalStatus.ACHIEVED
        
        if self.is_failed():
            return GoalStatus.FAILED
        
        if self.is_resource_exhausted():
            if self.valid_jobs_found > 0:
                return GoalStatus.PARTIALLY_ACHIEVED
            else:
                return GoalStatus.FAILED
        
        if self.valid_jobs_found > 0:
            return GoalStatus.IN_PROGRESS
        
        return GoalStatus.PENDING
    
    # ========================
    # Progress Metrics
    # ========================
    
    def progress_percentage(self) -> float:
        """
        Calculate progress towards the goal.
        
        Returns:
            Percentage (0-100) of goal completion
        """
        if self.target_valid_jobs == 0:
            return 100.0
        return min(100.0, (self.valid_jobs_found / self.target_valid_jobs) * 100)
    
    def current_error_rate(self) -> float:
        """
        Calculate current error rate.
        
        Returns:
            Error rate as a decimal (0.0-1.0)
        """
        if self.total_attempts == 0:
            return 0.0
        return self.errors_encountered / self.total_attempts
    
    def current_success_rate(self) -> float:
        """
        Calculate current success rate.
        
        Returns:
            Success rate as a decimal (0.0-1.0)
        """
        if self.total_attempts == 0:
            return 0.0
        return self.valid_jobs_found / self.total_attempts
    
    def elapsed_time_seconds(self) -> float:
        """
        Calculate elapsed execution time.
        
        Returns:
            Elapsed time in seconds, or 0 if not started
        """
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time
    
    def remaining_time_seconds(self) -> float:
        """
        Calculate remaining time before timeout.
        
        Returns:
            Remaining seconds, or inf if not started
        """
        if self.start_time is None:
            return float('inf')
        elapsed = time.time() - self.start_time
        return max(0, self.resources.max_execution_time_seconds - elapsed)
    
    def jobs_per_hour(self) -> float:
        """
        Calculate extraction rate.
        
        Returns:
            Jobs extracted per hour
        """
        elapsed_hours = self.elapsed_time_seconds() / 3600
        if elapsed_hours == 0:
            return 0.0
        return self.valid_jobs_found / elapsed_hours
    
    # ========================
    # State Updates
    # ========================
    
    def start(self):
        """Mark goal execution as started."""
        self.start_time = time.time()
    
    def complete(self):
        """Mark goal execution as complete."""
        self.end_time = time.time()
    
    def record_success(self, job_data: Dict[str, Any]):
        """
        Record a successful job extraction.
        
        Args:
            job_data: Extracted job information
        """
        self.valid_jobs_found += 1
        self.total_attempts += 1
        self.extracted_jobs.append(job_data)
    
    def record_failure(self, url: str, reason: str = ""):
        """
        Record a failed extraction attempt.
        
        Args:
            url: URL that failed
            reason: Optional failure reason
        """
        self.errors_encountered += 1
        self.total_attempts += 1
        self.failed_urls.append(url)
    
    def record_skip(self):
        """Record a skipped URL (no valid link found, but not an error)."""
        self.total_attempts += 1
    
    def record_duplicate(self, job_data: Dict[str, Any]):
        """
        Record a duplicate job found.
        
        Args:
            job_data: The duplicate job information
        """
        self.duplicates_found += 1
        self.valid_jobs_found += 1  # Still counts towards goal
        self.total_attempts += 1
        job_data['is_duplicate'] = True
        self.extracted_jobs.append(job_data)
    
    def record_request(self):
        """Increment request counter."""
        self.requests_made += 1
    
    # ========================
    # Reporting
    # ========================
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Generate a summary report of goal progress.
        
        Returns:
            Dictionary containing all metrics
        """
        return {
            'status': self.get_status().value,
            'progress': f"{self.progress_percentage():.1f}%",
            'valid_jobs': f"{self.valid_jobs_found}/{self.target_valid_jobs}",
            'success_rate': f"{self.current_success_rate() * 100:.1f}%",
            'error_rate': f"{self.current_error_rate() * 100:.1f}%",
            'duplicates': self.duplicates_found,
            'total_attempts': self.total_attempts,
            'requests_made': self.requests_made,
            'elapsed_time': f"{self.elapsed_time_seconds():.0f}s",
            'jobs_per_hour': f"{self.jobs_per_hour():.1f}",
            'remaining_time': f"{self.remaining_time_seconds():.0f}s"
        }
    
    def __str__(self) -> str:
        """Human-readable goal description."""
        summary = self.get_summary()
        return (
            f"Goal: Extract {self.target_valid_jobs} jobs | "
            f"Status: {summary['status']} | "
            f"Progress: {summary['progress']} | "
            f"Rate: {summary['jobs_per_hour']} jobs/hr"
        )


@dataclass
class SubGoal:
    """
    A sub-goal for hierarchical goal decomposition.
    
    Used for breaking down the main goal into smaller objectives,
    such as "Scan sitemap of domain X" or "Process page Y".
    """
    description: str
    parent_goal: Optional[ScrapingGoal] = None
    target_count: int = 1
    current_count: int = 0
    status: GoalStatus = GoalStatus.PENDING
    
    def is_achieved(self) -> bool:
        return self.current_count >= self.target_count
    
    def increment(self):
        self.current_count += 1
        if self.is_achieved():
            self.status = GoalStatus.ACHIEVED
        else:
            self.status = GoalStatus.IN_PROGRESS
