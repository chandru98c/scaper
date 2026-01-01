# CareerBoard Agent Architecture

## Overview

This document describes the transformation of the CareerBoard job scraper from a procedural script into a **Goal-Based Intelligent Agent**.

## Agent Classification

### Previous Implementation: Model-Based Reflex Agent (70%) + Script (30%)

The original implementation had:
- ✅ Internal state (seen_links)
- ✅ Condition-action rules (retry on 429)
- ❌ No explicit goals
- ❌ No dynamic planning
- ❌ Limited recovery

### New Implementation: Goal-Based Agent (100%)

The refactored system has:
- ✅ Explicit goal representation
- ✅ Internal world model
- ✅ Dynamic strategy planning
- ✅ Intelligent failure recovery
- ✅ Adaptive behavior

---

## PEAS Framework

### Performance Measure (P)
| Metric | Target |
|--------|--------|
| Unique jobs per hour | ≥ 30 |
| Precision | ≥ 95% |
| Error rate | ≤ 15% |
| Duplicate prevention | 100% |

### Environment (E)
- **Observability**: Partially observable (HTML only, no JS state)
- **Determinism**: Stochastic (A/B tests, dynamic content)
- **Episodic/Sequential**: Sequential (rate limits persist)
- **Static/Dynamic**: Dynamic (layouts change)
- **Challenges**: Rate limits, CAPTCHAs, layout changes, anti-bot

### Actuators (A)
- HTTP GET requests
- User-Agent rotation
- Request delays (politeness)
- File I/O (results, history)

### Sensors (S)
- HTML parsing (BeautifulSoup)
- XML parsing (sitemap)
- Date detection (meta tags, URL patterns)
- Link scoring (heuristic algorithm)

---

## Architecture Components

```
┌─────────────────────────────────────────────────────┐
│                   ORCHESTRATOR                       │
│                 (Main Control Loop)                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌───────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │   GOAL    │  │ WORLD MODEL │  │   PLANNER    │  │
│  │           │  │             │  │              │  │
│  │ • Target  │  │ • Sites     │  │ • Strategies │  │
│  │ • Progress│  │ • Threats   │  │ • Ranking    │  │
│  │ • Status  │  │ • History   │  │ • Replanning │  │
│  └───────────┘  └─────────────┘  └──────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │              RECOVERY ENGINE                  │  │
│  │                                              │  │
│  │  • Failure Classification                    │  │
│  │  • Decision Making (Retry/Switch/Abort)      │  │
│  │  • Backoff Calculation                       │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
├─────────────────────────────────────────────────────┤
│                    EXECUTORS                         │
│                                                     │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │  Sitemap   │  │   Auto     │  │    API       │  │
│  │  Crawler   │  │ Discovery  │  │  Extractor   │  │
│  └────────────┘  └────────────┘  └──────────────┘  │
│                                                     │
├─────────────────────────────────────────────────────┤
│                   EFFECTORS                          │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │              PoliteScraper                    │  │
│  │  • HTTP Requests                              │  │
│  │  • User-Agent Rotation                        │  │
│  │  • Exponential Backoff                        │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Module Descriptions

### 1. Goal Module (`goal.py`)
Explicit representation of what the agent is trying to achieve.

**Key Classes:**
- `ScrapingGoal`: Main goal with target, progress tracking, quality constraints
- `GoalStatus`: Enum (PENDING, IN_PROGRESS, ACHIEVED, FAILED)
- `QualityConstraints`: Min confidence, max error rate
- `ResourceLimits`: Max time, max requests

**Usage:**
```python
goal = ScrapingGoal(
    target_valid_jobs=50,
    quality=QualityConstraints(max_error_rate=0.15),
    resources=ResourceLimits(max_execution_time_seconds=3600)
)
```

### 2. World Model (`world_model.py`)
Internal representation of environment state.

**Key Classes:**
- `WorldModel`: Global state container
- `TargetSiteModel`: Per-site knowledge (threats, capabilities, selectors)
- `ThreatLevel`: Enum (NONE, LOW, MEDIUM, HIGH, BLOCKED)
- `SiteCapability`: Detected site features

**Features:**
- Threat level tracking per domain
- Strategy performance history
- Selector memory for adaptive extraction
- Persistence support

### 3. Strategy Planner (`planner.py`)
Dynamic strategy selection and ordering.

**Key Classes:**
- `StrategyPlanner`: Main planning logic
- `Plan`: Ordered list of strategies
- `Strategy`: Individual strategy with config
- `StrategyType`: Available strategies enum

**Strategies:**
1. `SITEMAP_CRAWL` - Parse sitemap.xml
2. `AUTO_DISCOVERY` - Paginate through listings
3. `API_EXTRACTION` - Use discovered API
4. `GOOGLE_CACHE` - Fallback to cached pages
5. `WAYBACK_MACHINE` - Archive.org fallback

### 4. Recovery Engine (`recovery.py`)
Intelligent failure handling.

**Key Classes:**
- `RecoveryEngine`: Main recovery logic
- `RecoveryDecision`: Action to take after failure
- `FailureType`: Classification of failures

**Failure Types:**
- `RATE_LIMITED` (429)
- `BLOCKED` (403)
- `CAPTCHA_DETECTED`
- `LAYOUT_CHANGED`
- `NETWORK_TIMEOUT`
- `AUTHENTICATION_REQUIRED`

**Recovery Actions:**
- Retry with backoff
- Rotate identity
- Switch strategy
- Abort with reason

### 5. Orchestrator (`orchestrator.py`)
Main control loop coordinating all components.

**Key Class:**
- `CareerBoardAgent`: Main agent class

**Control Loop:**
1. Initialize goal
2. Generate plan
3. Execute current strategy
4. On failure → Recovery decides action
5. On success → Update world model
6. Check goal → Continue or complete

---

## API Endpoints

### Agent Endpoint
```
GET /stream_agent
Parameters:
  - target_url: Starting URL (required)
  - start_date: YYYY-MM-DD
  - end_date: YYYY-MM-DD
  - target_jobs: Number to extract (default: 50)
  - max_time: Max minutes (default: 60)
```

### Agent Status
```
GET /api/agent/status
Returns: Agent system information
```

---

## Recovery Loop Pseudocode

```
FUNCTION recovery_loop(failure):
    
    1. CLASSIFY failure type
    
    2. CHECK abort conditions:
       - Too many consecutive failures → ABORT
       - Error rate exceeded → ABORT
       - Resources exhausted → ABORT (or PARTIAL)
    
    3. HANDLE specific failure:
       - RATE_LIMITED → Wait (exponential backoff), rotate identity
       - BLOCKED → Wait, rotate, switch to fallback
       - CAPTCHA → Skip, try next strategy
       - LAYOUT → Try alternative selectors
       - TIMEOUT → Retry with longer timeout
    
    4. SWITCH strategy if current exhausted
    
    5. DEFAULT: Retry with exponential backoff

    RETURN decision
```

---

## File Structure

```
scaper/
├── app.py                      # Flask routes + agent endpoint
├── services/
│   ├── http_client.py          # HTTP layer
│   ├── extractor.py            # Link extraction
│   ├── sitemap_parser.py       # Sitemap parsing
│   ├── auto_discovery/         # Pagination crawler
│   │   ├── runner.py
│   │   ├── pagination.py
│   │   └── extractor.py
│   └── agent/                  # ★ NEW AGENT MODULE ★
│       ├── __init__.py         # Exports
│       ├── goal.py             # Goal representation
│       ├── world_model.py      # Environment model
│       ├── planner.py          # Strategy planning
│       ├── recovery.py         # Failure handling
│       └── orchestrator.py     # Main agent loop
└── docs/
    └── AGENT_ARCHITECTURE.md   # This file
```

---

## Usage Examples

### Basic Usage
```python
from services.agent import CareerBoardAgent, ScrapingGoal

# Create agent with default goal (50 jobs)
agent = CareerBoardAgent()

# Run agent
for log in agent.run("https://example.com/jobs"):
    print(log)
```

### Custom Goal
```python
from services.agent import CareerBoardAgent, ScrapingGoal
from services.agent.goal import QualityConstraints, ResourceLimits

goal = ScrapingGoal(
    target_valid_jobs=100,
    quality=QualityConstraints(
        min_confidence_score=0.5,
        max_error_rate=0.10
    ),
    resources=ResourceLimits(
        max_execution_time_seconds=7200,
        max_requests_per_session=1000
    )
)

agent = CareerBoardAgent(goal=goal)
```

---

## Key Differences: Script vs Agent

| Aspect | Script | Agent |
|--------|--------|-------|
| Termination | When list exhausted | When goal achieved |
| Failure Response | Skip and continue | Analyze → Decide → Recover |
| Strategy Selection | User picks manually | Agent ranks dynamically |
| State Management | Minimal | Rich world model |
| Adaptability | None | Tries alternatives |
| Observability | Logs only | Structured metrics |

---

## References

1. Russell, S. & Norvig, P. (2021). *Artificial Intelligence: A Modern Approach* (4th ed.). Pearson.
   - Chapter 2: Intelligent Agents
   - Chapter 3: Solving Problems by Searching
   - Chapter 11: Planning and Acting in the Real World

2. Wooldridge, M. (2009). *An Introduction to MultiAgent Systems* (2nd ed.). Wiley.

---

## Version History

- **v1.0** - Procedural script with basic retry logic
- **v2.0** - Goal-Based Agent architecture (current)
