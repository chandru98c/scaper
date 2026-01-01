"""
Agent Orchestrator Module
=========================
The main control loop for the CareerBoard Goal-Based Agent.

This module integrates all agent components:
- Goal tracking
- World model updates
- Strategy planning
- Failure recovery
- Execution coordination
"""

from typing import Generator, Optional, Dict, Any, List
from datetime import datetime, timedelta
from urllib.parse import urlparse
import time
import os

from .goal import ScrapingGoal, GoalStatus
from .world_model import WorldModel, ThreatLevel
from .planner import StrategyPlanner, Plan, StrategyType
from .recovery import RecoveryEngine, RecoveryDecision, FailureType, classify_error


class CareerBoardAgent:
    """
    The Goal-Based Agent Orchestrator.
    
    Core Loop:
    1. Initialize Goal
    2. Generate Plan
    3. Execute Plan
    4. On Failure → Recovery Engine decides next action
    5. On Success → Update World Model, check Goal
    6. Repeat until Goal achieved or all strategies exhausted
    """
    
    # Shared Drive Path for duplicate detection
    SHARED_DRIVE_PATH = r"G:\My Drive\sharded_scaper\seen_apply_link.txt"
    LOCAL_FALLBACK_PATH = os.path.join(os.path.expanduser("~"), "Google Drive", "sharded_scaper", "seen_apply_link.txt")
    
    def __init__(
        self,
        goal: Optional[ScrapingGoal] = None,
        output_folder: str = "scraped_data"
    ):
        """
        Initialize the agent.
        
        Args:
            goal: Scraping goal (defaults to 50 jobs)
            output_folder: Folder for saving results
        """
        self.goal = goal or ScrapingGoal(target_valid_jobs=50)
        self.world_model = WorldModel()
        self.planner = StrategyPlanner(self.goal, self.world_model)
        self.recovery = RecoveryEngine(self.goal, self.world_model, self.planner)
        self.output_folder = output_folder
        
        # Lazy-load scraper to avoid circular imports
        self._scraper = None
        
        # Current execution state
        self._current_plan: Optional[Plan] = None
        self._new_apply_links: List[str] = []
    
    @property
    def scraper(self):
        """Lazy-load the scraper instance."""
        if self._scraper is None:
            from services.http_client import PoliteScraper
            self._scraper = PoliteScraper()
        return self._scraper
    
    def _get_shared_history_path(self) -> Optional[str]:
        """Get path to shared history file if available."""
        if os.path.exists(os.path.dirname(self.SHARED_DRIVE_PATH)):
            return self.SHARED_DRIVE_PATH
        if os.path.exists(os.path.dirname(self.LOCAL_FALLBACK_PATH)):
            return self.LOCAL_FALLBACK_PATH
        return None
    
    def run(
        self,
        target_url: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Main agent execution loop with SSE-compatible logging.
        
        Args:
            target_url: Starting URL for extraction
            start_date: Filter start date (YYYY-MM-DD)
            end_date: Filter end date (YYYY-MM-DD)
            
        Yields:
            Log messages for streaming to client
        """
        # Initialize
        self.goal.start()
        self.world_model.start_session()
        
        # Set date range on goal
        if start_date and end_date:
            self.goal.date_range = (start_date, end_date)
        else:
            # Default to last 7 days
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=7)
            self.goal.date_range = (
                start_dt.strftime("%Y-%m-%d"),
                end_dt.strftime("%Y-%m-%d")
            )
        
        yield f"[AGENT] CareerBoard Agent v2.0 initialized"
        yield f"[GOAL] Target: Extract {self.goal.target_valid_jobs} valid jobs"
        yield f"[GOAL] Date Range: {self.goal.date_range[0]} to {self.goal.date_range[1]}"
        yield f"[TARGET] {target_url}"
        
        # Load shared history
        history_path = self._get_shared_history_path()
        if history_path:
            loaded = self.world_model.load_shared_history(history_path)
            yield f"[HISTORY] Loaded {loaded} links from shared history"
        else:
            yield "[WARN] Shared Drive not found. Running in isolated mode."
        
        # Generate initial plan
        self._current_plan = self.planner.generate_plan(target_url)
        strategy_names = [s.name.value for s in self._current_plan.strategies]
        yield f"[PLAN] Generated {len(self._current_plan.strategies)} strategies: {strategy_names}"
        
        # Execute plan
        while self._current_plan.has_more() and not self._should_stop():
            current = self._current_plan.current_strategy()
            yield f"[EXECUTE] Strategy: {current.name.value}"
            yield f"[PROGRESS] {self.goal.progress_percentage():.1f}% complete ({self.goal.valid_jobs_found}/{self.goal.target_valid_jobs})"
            
            try:
                # Execute based on strategy type
                if current.name == StrategyType.SITEMAP_CRAWL:
                    for log in self._execute_sitemap(current.target_url):
                        yield log
                        if self.goal.is_achieved():
                            break
                
                elif current.name == StrategyType.AUTO_DISCOVERY:
                    for log in self._execute_auto_discovery(current.target_url):
                        yield log
                        if self.goal.is_achieved():
                            break
                
                # Check goal after each strategy
                if self.goal.is_achieved():
                    yield f"[SUCCESS] Goal achieved! Found {self.goal.valid_jobs_found} jobs."
                    break
                
                # Strategy completed normally
                self._current_plan.advance()
                self.recovery.reset_on_success()
                
            except Exception as e:
                # Classify failure and recover
                for log in self._handle_failure(e, self._current_plan):
                    yield log
        
        # Finalize
        self.goal.complete()
        
        # Save results
        if self.goal.extracted_jobs:
            for log in self._save_results():
                yield log
        
        # Save new links to shared history
        if self._new_apply_links and history_path:
            self.world_model.save_to_shared_history(history_path, self._new_apply_links)
            yield f"[HISTORY] Saved {len(self._new_apply_links)} new links to shared history"
        
        # Final status
        summary = self.goal.get_summary()
        yield f"[COMPLETE] Status: {summary['status']}"
        yield f"[STATS] Jobs: {summary['valid_jobs']} | Success Rate: {summary['success_rate']} | Time: {summary['elapsed_time']}"
    
    def _should_stop(self) -> bool:
        """Check if agent should terminate."""
        if self.goal.is_achieved():
            return True
        if self.goal.is_resource_exhausted():
            return True
        return False
    
    def _handle_failure(self, error: Exception, plan: Plan) -> Generator[str, None, None]:
        """Handle a failure and decide next action."""
        failure_type = classify_error(error)
        yield f"[ERROR] {failure_type.value}: {str(error)[:100]}"
        
        decision = self.recovery.analyze_and_decide(
            failure_type,
            plan,
            {"error": str(error)}
        )
        
        yield decision.log_message
        
        if not decision.should_retry:
            return
        
        if decision.wait_seconds > 0:
            yield f"[WAIT] Sleeping for {decision.wait_seconds:.1f}s..."
            time.sleep(decision.wait_seconds)
        
        if decision.rotate_identity:
            yield "[IDENTITY] Rotating User-Agent..."
            # The scraper rotates UA on each request automatically
        
        if decision.new_plan:
            self._current_plan = decision.new_plan
            yield f"[REPLAN] New plan with {len(self._current_plan.strategies)} strategies"
    
    def _execute_sitemap(self, sitemap_url: str) -> Generator[str, None, None]:
        """Execute sitemap crawl strategy."""
        from services.sitemap_parser import get_new_job_urls
        from services.extractor import extract_official_link
        
        yield f"[SITEMAP] Fetching: {sitemap_url}"
        
        start_date, end_date = self.goal.date_range
        items = get_new_job_urls(self.scraper, sitemap_url, start_date, end_date)
        
        if not items:
            yield "[SITEMAP] No URLs found matching date range"
            return
        
        yield f"[SITEMAP] Found {len(items)} URLs to process"
        
        for i, item in enumerate(items):
            if self.goal.is_achieved() or self.goal.is_resource_exhausted():
                break
            
            url = item['url']
            post_date = item['date']
            
            self.goal.record_request()
            self.world_model.mark_url_visited(url)
            
            yield f"[{i+1}/{len(items)}] Checking: {url[:60]}..."
            
            try:
                data = extract_official_link(self.scraper, url)
                
                if data:
                    apply_link = data['link'].strip()
                    
                    # Duplicate check
                    if self.world_model.is_apply_link_seen(apply_link):
                        yield f"[DUPLICATE] {data['title'][:40]}..."
                        self.goal.record_duplicate({
                            'Date Posted': post_date,
                            'Job Title': data['title'],
                            'Apply Link': apply_link,
                            'Link Text': data['text'],
                            'Context': data['match'],
                            'Source Post': url,
                            'Status': 'Duplicate'
                        })
                    else:
                        yield f"[FOUND] ({self.goal.valid_jobs_found + 1}/{self.goal.target_valid_jobs}) {data['title'][:40]}..."
                        
                        job_data = {
                            'Date Posted': post_date,
                            'Job Title': data['title'],
                            'Apply Link': apply_link,
                            'Link Text': data['text'],
                            'Context': data['match'],
                            'Source Post': url,
                            'Status': 'New'
                        }
                        
                        self.goal.record_success(job_data)
                        self.world_model.add_apply_link(apply_link)
                        self._new_apply_links.append(apply_link)
                else:
                    self.goal.record_skip()
                    
            except Exception as e:
                yield f"[WARN] Error processing URL: {str(e)[:50]}"
                self.goal.record_failure(url, str(e))
    
    def _execute_auto_discovery(self, homepage_url: str) -> Generator[str, None, None]:
        """Execute auto-discovery strategy."""
        from services.auto_discovery.runner import AutoDiscoveryRunner
        
        yield f"[AUTO] Starting Auto-Discovery: {homepage_url}"
        
        start_date, end_date = self.goal.date_range
        runner = AutoDiscoveryRunner(self.scraper)
        
        for log in runner.run(homepage_url, start_date, end_date, self.output_folder):
            yield f"[AUTO] {log}"
            
            # Parse log to update goal progress
            if "[FOUND]" in log:
                self.goal.valid_jobs_found += 1
            elif "[DOWNLOAD]" in log:
                # Auto-discovery saves its own file
                pass
    
    def _save_results(self) -> Generator[str, None, None]:
        """Save extracted jobs to Excel file."""
        import pandas as pd
        
        if not self.goal.extracted_jobs:
            yield "[SAVE] No jobs to save"
            return
        
        os.makedirs(self.output_folder, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agent_jobs_{timestamp}.xlsx"
        filepath = os.path.join(self.output_folder, filename)
        
        df = pd.DataFrame(self.goal.extracted_jobs)
        
        # Styling for duplicates
        def highlight_duplicates(row):
            if row.get('Status') == 'Duplicate':
                return ['background-color: #ffcccc'] * len(row)
            return [''] * len(row)
        
        try:
            styler = df.style.apply(highlight_duplicates, axis=1)
            styler.to_excel(filepath, index=False, engine='openpyxl')
        except Exception:
            df.to_excel(filepath, index=False)
        
        yield f"[SAVE] Saved {len(self.goal.extracted_jobs)} jobs to {filename}"
        yield f"[DOWNLOAD] {filename}"
    
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            'goal': self.goal.get_summary(),
            'world_model': self.world_model.get_summary(),
            'recovery': self.recovery.get_failure_summary(),
            'current_plan': str(self._current_plan) if self._current_plan else "No plan"
        }


def create_agent(
    target_jobs: int = 50,
    max_time_minutes: int = 60,
    max_error_rate: float = 0.15
) -> CareerBoardAgent:
    """
    Factory function to create a configured agent.
    
    Args:
        target_jobs: Number of jobs to extract
        max_time_minutes: Maximum execution time
        max_error_rate: Maximum acceptable error rate
        
    Returns:
        Configured CareerBoardAgent instance
    """
    from .goal import QualityConstraints, ResourceLimits
    
    goal = ScrapingGoal(
        target_valid_jobs=target_jobs,
        quality=QualityConstraints(max_error_rate=max_error_rate),
        resources=ResourceLimits(max_execution_time_seconds=max_time_minutes * 60)
    )
    
    return CareerBoardAgent(goal=goal)
