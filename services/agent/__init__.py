"""
CareerBoard Agent Module
========================
A Goal-Based Intelligent Agent for autonomous job scraping.

This module transforms the procedural scraper into an AI agent that:
- Maintains explicit goals and tracks progress
- Builds an internal world model of target sites
- Plans and selects strategies dynamically
- Recovers from failures intelligently

Components:
- goal.py: Goal representation and progress tracking
- world_model.py: Internal state and environment modeling
- planner.py: Strategy selection and planning
- recovery.py: Failure analysis and recovery decisions
- orchestrator.py: Main agent control loop

Author: CareerBoard Team
Version: 2.0.0 (Agent-Based Architecture)
"""

from .goal import ScrapingGoal, GoalStatus
from .world_model import WorldModel, TargetSiteModel, ThreatLevel, SiteCapability
from .planner import StrategyPlanner, Plan, Strategy, StrategyType
from .recovery import RecoveryEngine, RecoveryDecision, FailureType
from .orchestrator import CareerBoardAgent

__all__ = [
    # Goal Module
    'ScrapingGoal',
    'GoalStatus',
    
    # World Model
    'WorldModel',
    'TargetSiteModel',
    'ThreatLevel',
    'SiteCapability',
    
    # Planner
    'StrategyPlanner',
    'Plan',
    'Strategy',
    'StrategyType',
    
    # Recovery
    'RecoveryEngine',
    'RecoveryDecision',
    'FailureType',
    
    # Orchestrator
    'CareerBoardAgent',
]

__version__ = '2.0.0'
