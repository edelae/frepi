# Frepi Agent: High-Iteration Development Architecture

## 1. Vision

Build a self-improving system where user feedback automatically triggers AI-driven code modifications, testing, and deployment - creating a rapid iteration cycle that continuously improves the product based on real user needs.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CONTINUOUS IMPROVEMENT LOOP                          │
│                                                                         │
│   Users → Feedback → AI Analysis → Code Changes → Tests → Deploy       │
│     ↑                                                         │        │
│     └─────────────────────────────────────────────────────────┘        │
│                         (repeat)                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Overview

### 2.1 High-Level Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   COLLECT   │───▶│   ANALYZE   │───▶│   MODIFY    │───▶│    TEST     │  │
│  │  Feedback   │    │  & Classify │    │    Code     │    │  & Validate │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘  │
│         ▲                                                        │         │
│         │                                                        ▼         │
│         │                                              ┌─────────────────┐ │
│         │                                              │  Tests Pass?    │ │
│         │                                              └────────┬────────┘ │
│         │                                                       │          │
│         │                              ┌────────────────────────┼──────┐   │
│         │                              │                        │      │   │
│         │                              ▼                        ▼      │   │
│  ┌─────────────┐                ┌─────────────┐          ┌──────────┐ │   │
│  │   MONITOR   │◀───────────────│   DEPLOY    │◀─────YES─│  PASS    │ │   │
│  │  & Learn    │                │  to Prod    │          └──────────┘ │   │
│  └─────────────┘                └─────────────┘                       │   │
│                                                                       │   │
│                                       ┌──────────┐                    │   │
│                                       │  FAIL    │◀───────────────NO──┘   │
│                                       └────┬─────┘                        │
│                                            │                              │
│                                            ▼                              │
│                                   ┌─────────────────┐                     │
│                                   │  RETRY LOOP     │                     │
│                                   │  (max 3 attempts)│                    │
│                                   │                 │                     │
│                                   │  Analyze error  │                     │
│                                   │  Modify code    │                     │
│                                   │  Re-test        │                     │
│                                   └────────┬────────┘                     │
│                                            │                              │
│                                            ▼                              │
│                                   ┌─────────────────┐                     │
│                                   │ Still failing?  │                     │
│                                   │ → Human review  │                     │
│                                   └─────────────────┘                     │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Feedback Collector** | Capture user feedback from multiple channels | Supabase + Webhooks |
| **Feedback Analyzer** | Classify and prioritize feedback | Claude API |
| **Code Modifier** | Generate code changes based on feedback | Claude Code SDK |
| **Test Runner** | Execute tests and validate changes | pytest + Custom assertions |
| **Deployer** | Push to GitHub, trigger CI/CD | GitHub Actions |
| **Monitor** | Track deployment health and user satisfaction | Logs + Metrics |

---

## 3. Component Details

### 3.1 Feedback Collector

**Purpose:** Capture feedback from all user touchpoints.

**Sources:**
```
┌─────────────────────────────────────────────────────────┐
│                   FEEDBACK SOURCES                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📱 In-App Feedback                                     │
│     └─ User rates response: 👍 / 👎                     │
│     └─ User provides comment: "Não entendi a resposta"  │
│                                                         │
│  💬 Conversation Signals                                │
│     └─ User repeats question (confusion)                │
│     └─ User says "não era isso" (wrong response)        │
│     └─ User abandons flow mid-conversation              │
│     └─ User asks for clarification                      │
│                                                         │
│  📊 Behavioral Metrics                                  │
│     └─ Response time > threshold                        │
│     └─ Agent error/retry count                          │
│     └─ Flow completion rate                             │
│     └─ User satisfaction score over time                │
│                                                         │
│  🐛 Error Logs                                          │
│     └─ Agent exceptions                                 │
│     └─ Database query failures                          │
│     └─ Tool execution errors                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Database Schema:**

```sql
CREATE TABLE feedback_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source identification
    source_type VARCHAR NOT NULL,  -- 'rating', 'comment', 'signal', 'metric', 'error'
    session_id VARCHAR REFERENCES line_sessions(session_id),
    restaurant_id INTEGER REFERENCES restaurants(id),

    -- Feedback content
    feedback_type VARCHAR NOT NULL,  -- 'positive', 'negative', 'neutral', 'bug', 'feature_request'
    raw_content TEXT,                -- Original user message or error log
    context JSONB,                   -- Conversation context, agent state

    -- Classification (filled by AI)
    category VARCHAR,                -- 'prompt', 'tool', 'flow', 'ui', 'performance', 'other'
    severity VARCHAR,                -- 'critical', 'high', 'medium', 'low'
    affected_component VARCHAR,      -- 'customer_agent', 'purchase_order', 'price_updater', etc.
    suggested_action TEXT,           -- AI-generated suggestion

    -- Processing status
    status VARCHAR DEFAULT 'pending', -- 'pending', 'analyzing', 'implementing', 'testing', 'deployed', 'rejected'
    processed_at TIMESTAMP,
    implemented_in_commit VARCHAR,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE feedback_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Grouping
    feedback_ids UUID[],
    common_theme VARCHAR,
    priority_score NUMERIC,

    -- Implementation tracking
    status VARCHAR DEFAULT 'pending',
    claude_session_id VARCHAR,       -- Claude Code session for this batch
    commits_made VARCHAR[],
    tests_passed BOOLEAN,
    retry_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

---

### 3.2 Feedback Analyzer

**Purpose:** Classify feedback, identify patterns, and prioritize for implementation.

**Process:**

```python
# analyzer/feedback_analyzer.py

from claude_agent_sdk import query, ClaudeAgentOptions

ANALYZER_PROMPT = """
You are a feedback analysis specialist for Frepi, a restaurant purchasing assistant.

Your job is to:
1. Classify the feedback type and severity
2. Identify which component is affected
3. Suggest specific code changes needed
4. Group related feedback items into actionable batches

Categories:
- PROMPT: Issues with agent responses, tone, language, clarity
- TOOL: Issues with database queries, calculations, matching
- FLOW: Issues with conversation flow, menu navigation, state management
- PERFORMANCE: Slow responses, timeouts, resource issues
- FEATURE: Missing functionality users are requesting
- BUG: Clear errors or incorrect behavior

Severity levels:
- CRITICAL: System broken, users cannot complete core tasks
- HIGH: Major inconvenience, workaround exists but painful
- MEDIUM: Minor issue, doesn't block core functionality
- LOW: Nice to have improvement, cosmetic issues

Output JSON format:
{
    "classification": {
        "category": "PROMPT|TOOL|FLOW|PERFORMANCE|FEATURE|BUG",
        "severity": "CRITICAL|HIGH|MEDIUM|LOW",
        "affected_component": "component_name",
        "confidence": 0.0-1.0
    },
    "analysis": {
        "root_cause": "Brief explanation of why this is happening",
        "user_impact": "How this affects the user experience",
        "frequency_estimate": "one-off|occasional|frequent|constant"
    },
    "suggested_changes": [
        {
            "file": "path/to/file.py",
            "type": "modify|add|delete",
            "description": "What to change",
            "priority": 1
        }
    ],
    "related_feedback_patterns": ["pattern1", "pattern2"],
    "implementation_complexity": "trivial|simple|moderate|complex"
}
"""

async def analyze_feedback(feedback_items: list) -> dict:
    """Analyze a batch of feedback items and return classification + suggestions."""

    context = "\n\n".join([
        f"Feedback #{i+1}:\n"
        f"Type: {item['feedback_type']}\n"
        f"Content: {item['raw_content']}\n"
        f"Context: {item['context']}"
        for i, item in enumerate(feedback_items)
    ])

    async for message in query(
        prompt=f"Analyze this user feedback:\n\n{context}",
        options=ClaudeAgentOptions(
            system_prompt=ANALYZER_PROMPT,
            allowed_tools=["Read"],  # Can read codebase for context
        )
    ):
        if hasattr(message, 'result'):
            return parse_analysis(message.result)
```

**Batching Logic:**

```python
# analyzer/batcher.py

async def create_implementation_batches(analyzed_feedback: list) -> list:
    """
    Group related feedback into implementation batches.

    Rules:
    1. Same component + same category = same batch
    2. CRITICAL severity = immediate single-item batch
    3. Max 5 items per batch (manageable scope)
    4. HIGH severity items processed before MEDIUM/LOW
    """

    # Priority queue
    batches = []

    # Critical items get their own batch
    critical = [f for f in analyzed_feedback if f['severity'] == 'CRITICAL']
    for item in critical:
        batches.append({
            'feedback_ids': [item['id']],
            'priority_score': 100,
            'common_theme': item['classification']['category'],
            'status': 'pending'
        })

    # Group remaining by component + category
    remaining = [f for f in analyzed_feedback if f['severity'] != 'CRITICAL']
    grouped = group_by_component_and_category(remaining)

    for key, items in grouped.items():
        # Split into batches of max 5
        for chunk in chunks(items, 5):
            priority = calculate_priority(chunk)
            batches.append({
                'feedback_ids': [i['id'] for i in chunk],
                'priority_score': priority,
                'common_theme': key,
                'status': 'pending'
            })

    return sorted(batches, key=lambda x: -x['priority_score'])
```

---

### 3.3 Code Modifier (Claude Code Integration)

**Purpose:** Automatically generate and apply code changes based on analyzed feedback.

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                     CODE MODIFIER ENGINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input:                                                         │
│  ├─ Feedback batch with analysis                                │
│  ├─ Suggested changes                                           │
│  └─ Current codebase context                                    │
│                                                                 │
│  Process:                                                       │
│  1. Read relevant files (prompts, tools, subagents)             │
│  2. Understand current implementation                           │
│  3. Generate specific code changes                              │
│  4. Apply changes using Edit tool                               │
│  5. Generate/update tests for changes                           │
│                                                                 │
│  Output:                                                        │
│  ├─ Modified files                                              │
│  ├─ New/updated test cases                                      │
│  └─ Change summary for commit message                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
# modifier/code_modifier.py

import subprocess
from pathlib import Path

CODE_MODIFIER_PROMPT = """
You are a senior Python developer working on Frepi, a restaurant purchasing assistant.

Your task is to implement code changes based on user feedback analysis.

RULES:
1. Make minimal, focused changes that address the specific feedback
2. Follow existing code patterns and style
3. Always add or update tests for your changes
4. Never break existing functionality
5. Add clear comments explaining why changes were made

CODEBASE STRUCTURE:
- frepi_agent/prompts/ - Agent system prompts (modify for response issues)
- frepi_agent/tools/ - Database operations (modify for query issues)
- frepi_agent/subagents/ - Subagent definitions (modify for flow issues)
- tests/ - Test files (always update when making changes)

CHANGE TYPES:
- PROMPT_FIX: Modify system prompts to improve responses
- TOOL_FIX: Fix database queries or calculations
- FLOW_FIX: Adjust conversation flow or state management
- NEW_FEATURE: Add new functionality
- BUG_FIX: Fix errors or incorrect behavior

After making changes, summarize what you changed in this format:
---CHANGE_SUMMARY---
Files modified: [list]
Tests added/modified: [list]
Commit message: [conventional commit format]
---END_SUMMARY---
"""

async def implement_changes(batch: dict, max_retries: int = 3) -> dict:
    """
    Use Claude Code to implement changes for a feedback batch.

    Returns:
        {
            'success': bool,
            'files_modified': list,
            'tests_added': list,
            'commit_message': str,
            'error': str or None
        }
    """

    # Prepare context
    feedback_context = prepare_feedback_context(batch)

    # Run Claude Code session
    result = await run_claude_code_session(
        prompt=f"""
        Implement the following changes based on user feedback:

        {feedback_context}

        Read the relevant files, make the necessary changes, and update tests.
        """,
        system_prompt=CODE_MODIFIER_PROMPT,
        allowed_tools=["Read", "Edit", "Write", "Glob", "Grep", "Bash"],
        working_directory=Path(__file__).parent.parent
    )

    return parse_modification_result(result)


async def run_claude_code_session(prompt: str, **options) -> str:
    """Execute a Claude Code session and return the result."""

    # Option 1: Use Claude Agent SDK directly
    from claude_agent_sdk import query, ClaudeAgentOptions

    result_text = ""
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(**options)
    ):
        if hasattr(message, 'result'):
            result_text = message.result

    return result_text
```

**Retry Logic:**

```python
# modifier/retry_handler.py

async def implement_with_retry(batch: dict) -> dict:
    """
    Implement changes with automatic retry on test failure.

    Strategy:
    1. First attempt: Implement based on original analysis
    2. On failure: Analyze test errors, adjust approach
    3. Max 3 retries before escalating to human review
    """

    max_retries = 3
    attempt = 0
    last_error = None

    while attempt < max_retries:
        attempt += 1

        # Implement changes
        if attempt == 1:
            result = await implement_changes(batch)
        else:
            # Include previous error context for retry
            result = await implement_changes(
                batch,
                previous_error=last_error,
                attempt_number=attempt
            )

        if not result['success']:
            last_error = result['error']
            continue

        # Run tests
        test_result = await run_tests(result['tests_added'])

        if test_result['passed']:
            # Success! Commit and prepare for deployment
            return {
                'success': True,
                'commit': await create_commit(result),
                'attempts': attempt
            }
        else:
            # Tests failed - prepare error context for retry
            last_error = {
                'test_output': test_result['output'],
                'failed_tests': test_result['failed'],
                'error_messages': test_result['errors']
            }

    # Max retries exceeded - escalate to human
    return {
        'success': False,
        'error': 'Max retries exceeded',
        'last_error': last_error,
        'requires_human_review': True,
        'attempts': attempt
    }
```

---

### 3.4 Test Runner

**Purpose:** Validate that code changes work correctly and don't break existing functionality.

**Test Categories:**

```
┌─────────────────────────────────────────────────────────────────┐
│                        TEST PYRAMID                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                        ┌─────────┐                              │
│                       /  E2E     \                              │
│                      /  Tests     \                             │
│                     / (10% coverage)\                           │
│                    /─────────────────\                          │
│                   /   Integration     \                         │
│                  /     Tests           \                        │
│                 /    (30% coverage)     \                       │
│                /─────────────────────────\                      │
│               /       Unit Tests          \                     │
│              /       (60% coverage)        \                    │
│             /───────────────────────────────\                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Test Structure:**

```python
# tests/conftest.py

import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for unit tests."""
    client = AsyncMock()
    client.table.return_value.select.return_value.execute.return_value = {
        'data': [],
        'error': None
    }
    return client

@pytest.fixture
def sample_restaurant_context():
    """Standard restaurant context for tests."""
    return {
        'restaurant_id': 1,
        'restaurant_name': 'Restaurante Teste',
        'person_id': 1,
        'person_name': 'Maria',
        'setup_complete': True
    }

@pytest.fixture
def sample_products():
    """Sample products for testing."""
    return [
        {'id': 1, 'name': 'Picanha Friboi 10kg', 'price': 43.50},
        {'id': 2, 'name': 'Arroz Camil 5kg', 'price': 28.90},
    ]
```

```python
# tests/test_agent_responses.py

import pytest
from frepi_agent.agent import run_customer_agent

class TestMenuDisplay:
    """Tests for 4-option menu display requirement."""

    @pytest.mark.asyncio
    async def test_greeting_shows_menu(self, sample_restaurant_context):
        """Menu must appear after greeting."""
        response = await run_customer_agent("Oi", sample_restaurant_context)

        assert "1️⃣ Fazer uma compra" in response.text
        assert "2️⃣ Atualizar preços" in response.text
        assert "3️⃣ Registrar" in response.text
        assert "4️⃣ Configurar" in response.text

    @pytest.mark.asyncio
    async def test_menu_after_task_completion(self, sample_restaurant_context):
        """Menu must appear after completing any task."""
        response = await run_customer_agent(
            "Quanto custa picanha?",
            sample_restaurant_context
        )

        # Should have price info AND menu
        assert "R$" in response.text
        assert "1️⃣ Fazer uma compra" in response.text


class TestProductMatching:
    """Tests for vector search product matching."""

    @pytest.mark.asyncio
    async def test_exact_match_high_confidence(self, mock_supabase):
        """Exact product name should return HIGH confidence."""
        result = await search_products("Picanha Friboi 10kg")

        assert result['matches'][0]['confidence'] == 'HIGH'
        assert result['matches'][0]['similarity'] > 0.85

    @pytest.mark.asyncio
    async def test_fuzzy_match_medium_confidence(self, mock_supabase):
        """Similar product should return MEDIUM confidence."""
        result = await search_products("carne para churrasco")

        assert any(m['confidence'] == 'MEDIUM' for m in result['matches'])

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, mock_supabase):
        """Unknown product should return no matches."""
        result = await search_products("xyzabc123")

        assert len(result['matches']) == 0 or all(
            m['confidence'] == 'LOW' for m in result['matches']
        )


class TestPriceValidation:
    """Tests for price validation before orders."""

    @pytest.mark.asyncio
    async def test_warns_on_expired_prices(self, mock_supabase, sample_products):
        """Should warn when prices are >30 days old."""
        # Mock old prices
        mock_supabase.table.return_value.select.return_value.execute.return_value = {
            'data': [{'effective_date': '2024-01-01', 'unit_price': 43.50}]
        }

        result = await validate_prices([1])

        assert result['has_warnings'] is True
        assert 'expired' in result['warnings'][0].lower() or 'days' in result['warnings'][0]

    @pytest.mark.asyncio
    async def test_blocks_order_without_prices(self, mock_supabase):
        """Should not allow order for products without pricing."""
        # Mock no prices
        mock_supabase.table.return_value.select.return_value.execute.return_value = {
            'data': []
        }

        result = await validate_prices([999])

        assert result['can_proceed'] is False
        assert len(result['products_without_pricing']) > 0


class TestPortugueseLanguage:
    """Tests for Portuguese language requirements."""

    @pytest.mark.asyncio
    async def test_responses_in_portuguese(self, sample_restaurant_context):
        """All responses should be in Portuguese."""
        response = await run_customer_agent("Hello", sample_restaurant_context)

        # Should respond in Portuguese even if user writes in English
        portuguese_words = ['fazer', 'compra', 'preços', 'fornecedor', 'preferências']
        assert any(word in response.text.lower() for word in portuguese_words)

    @pytest.mark.asyncio
    async def test_currency_format_brazilian(self, sample_restaurant_context):
        """Currency should use R$ format."""
        response = await run_customer_agent(
            "Quanto custa picanha?",
            sample_restaurant_context
        )

        assert "R$" in response.text
```

**Test Runner Script:**

```python
# runner/test_runner.py

import subprocess
import json
from pathlib import Path

async def run_tests(test_files: list = None) -> dict:
    """
    Run pytest and return results.

    Args:
        test_files: Specific test files to run, or None for all tests

    Returns:
        {
            'passed': bool,
            'total': int,
            'passed_count': int,
            'failed_count': int,
            'failed': list of failed test names,
            'errors': list of error messages,
            'output': full pytest output
        }
    """

    cmd = ['python', '-m', 'pytest', '-v', '--tb=short', '--json-report']

    if test_files:
        cmd.extend(test_files)
    else:
        cmd.append('tests/')

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    # Parse JSON report
    report_path = Path('.report.json')
    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)

        return {
            'passed': report['summary']['passed'] == report['summary']['total'],
            'total': report['summary']['total'],
            'passed_count': report['summary']['passed'],
            'failed_count': report['summary']['failed'],
            'failed': [t['nodeid'] for t in report['tests'] if t['outcome'] == 'failed'],
            'errors': [t['call']['longrepr'] for t in report['tests'] if t['outcome'] == 'failed'],
            'output': result.stdout + result.stderr
        }

    # Fallback to parsing output
    return {
        'passed': result.returncode == 0,
        'output': result.stdout + result.stderr,
        'errors': [result.stderr] if result.returncode != 0 else []
    }
```

---

### 3.5 Deployer

**Purpose:** Push validated changes to GitHub and trigger deployment.

**GitHub Actions Workflow:**

```yaml
# .github/workflows/auto-deploy.yml

name: Auto-Deploy from Feedback

on:
  push:
    branches:
      - feedback-improvements/*
  workflow_dispatch:
    inputs:
      batch_id:
        description: 'Feedback batch ID'
        required: true

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-json-report

      - name: Run unit tests
        run: pytest tests/ -v --json-report

      - name: Run integration tests
        run: pytest tests/integration/ -v --json-report
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Upload test results
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: .report.json

  deploy-staging:
    needs: validate
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to staging
        run: |
          # Deploy to staging environment
          echo "Deploying to staging..."
          # Add your staging deployment commands here

      - name: Run smoke tests
        run: |
          # Quick validation that staging works
          python scripts/smoke_test.py --env staging

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to production
        run: |
          echo "Deploying to production..."
          # Add your production deployment commands here

      - name: Notify completion
        run: |
          # Update feedback batch status
          python scripts/update_batch_status.py --batch-id ${{ github.event.inputs.batch_id }} --status deployed
```

**Deployment Script:**

```python
# deployer/github_deployer.py

import subprocess
from datetime import datetime

async def deploy_changes(result: dict, batch: dict) -> dict:
    """
    Create branch, commit changes, push, and create PR.

    Args:
        result: Output from code modifier (files_modified, commit_message)
        batch: Feedback batch being implemented

    Returns:
        {
            'success': bool,
            'branch': str,
            'commit_sha': str,
            'pr_url': str or None,
            'error': str or None
        }
    """

    batch_id = batch['id'][:8]
    timestamp = datetime.now().strftime('%Y%m%d-%H%M')
    branch_name = f"feedback-improvements/{batch_id}-{timestamp}"

    try:
        # Create and checkout branch
        subprocess.run(['git', 'checkout', '-b', branch_name], check=True)

        # Stage all changes
        subprocess.run(['git', 'add', '-A'], check=True)

        # Commit with structured message
        commit_message = f"""feat: {result['commit_message']}

Feedback batch: {batch['id']}
Theme: {batch['common_theme']}
Priority: {batch['priority_score']}
Feedback items: {len(batch['feedback_ids'])}

Automated implementation via Frepi Iteration Engine
"""
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)

        # Get commit SHA
        commit_sha = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()

        # Push branch
        subprocess.run(['git', 'push', '-u', 'origin', branch_name], check=True)

        # Create PR using GitHub CLI
        pr_result = subprocess.run(
            [
                'gh', 'pr', 'create',
                '--title', f"[Auto] {result['commit_message']}",
                '--body', f"""
## Automated Improvement

This PR was automatically generated based on user feedback.

### Feedback Summary
- **Batch ID:** {batch['id']}
- **Theme:** {batch['common_theme']}
- **Priority Score:** {batch['priority_score']}
- **Items Addressed:** {len(batch['feedback_ids'])}

### Changes Made
{chr(10).join(f'- {f}' for f in result['files_modified'])}

### Tests
{chr(10).join(f'- {t}' for t in result['tests_added'])}

---
*This PR was created automatically by the Frepi Iteration Engine.*
""",
                '--base', 'main'
            ],
            capture_output=True,
            text=True
        )

        pr_url = pr_result.stdout.strip() if pr_result.returncode == 0 else None

        return {
            'success': True,
            'branch': branch_name,
            'commit_sha': commit_sha,
            'pr_url': pr_url
        }

    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        # Return to main branch
        subprocess.run(['git', 'checkout', 'main'], check=False)
```

---

### 3.6 Monitor

**Purpose:** Track deployment health and measure improvement impact.

```python
# monitor/health_monitor.py

from datetime import datetime, timedelta

async def monitor_deployment(batch_id: str, duration_hours: int = 24) -> dict:
    """
    Monitor a deployment for the specified duration.

    Tracks:
    - Error rates (should decrease)
    - User satisfaction (should improve)
    - Related feedback (should decrease)
    - Performance metrics

    Returns:
        {
            'deployment_healthy': bool,
            'metrics': {...},
            'recommendation': 'keep' | 'rollback' | 'needs_investigation'
        }
    """

    batch = await get_batch(batch_id)
    deployed_at = batch['completed_at']

    # Get metrics before and after deployment
    before_window = (deployed_at - timedelta(days=7), deployed_at)
    after_window = (deployed_at, datetime.now())

    metrics_before = await get_metrics(batch['common_theme'], before_window)
    metrics_after = await get_metrics(batch['common_theme'], after_window)

    # Calculate improvement
    error_rate_change = (
        (metrics_after['error_rate'] - metrics_before['error_rate'])
        / metrics_before['error_rate']
    ) * 100 if metrics_before['error_rate'] > 0 else 0

    satisfaction_change = (
        metrics_after['satisfaction_avg'] - metrics_before['satisfaction_avg']
    )

    related_feedback_change = (
        (metrics_after['related_feedback_count'] - metrics_before['related_feedback_count'])
        / metrics_before['related_feedback_count']
    ) * 100 if metrics_before['related_feedback_count'] > 0 else 0

    # Determine health
    is_healthy = (
        error_rate_change <= 10 and  # Error rate didn't increase significantly
        satisfaction_change >= -0.1 and  # Satisfaction didn't drop
        related_feedback_change <= 20  # Not getting more of same feedback
    )

    # Recommendation
    if error_rate_change > 50 or satisfaction_change < -0.5:
        recommendation = 'rollback'
    elif not is_healthy:
        recommendation = 'needs_investigation'
    else:
        recommendation = 'keep'

    return {
        'deployment_healthy': is_healthy,
        'metrics': {
            'error_rate_change': f"{error_rate_change:+.1f}%",
            'satisfaction_change': f"{satisfaction_change:+.2f}",
            'related_feedback_change': f"{related_feedback_change:+.1f}%"
        },
        'recommendation': recommendation
    }
```

---

## 4. Complete Pipeline

### 4.1 Orchestrator

```python
# orchestrator/pipeline.py

import asyncio
from datetime import datetime

async def run_iteration_pipeline():
    """
    Main orchestrator that runs the complete iteration cycle.

    This runs on a schedule (e.g., every hour) or can be triggered manually.
    """

    print(f"[{datetime.now()}] Starting iteration pipeline...")

    # Step 1: Collect pending feedback
    pending_feedback = await get_pending_feedback(limit=50)

    if not pending_feedback:
        print("No pending feedback to process.")
        return

    print(f"Found {len(pending_feedback)} pending feedback items.")

    # Step 2: Analyze and classify
    analyzed = []
    for item in pending_feedback:
        analysis = await analyze_feedback([item])
        analyzed.append({**item, **analysis})
        await update_feedback_status(item['id'], 'analyzed')

    # Step 3: Create implementation batches
    batches = await create_implementation_batches(analyzed)
    print(f"Created {len(batches)} implementation batches.")

    # Step 4: Process batches by priority
    for batch in batches:
        print(f"Processing batch: {batch['common_theme']} (priority: {batch['priority_score']})")

        # Save batch to database
        batch_id = await save_batch(batch)

        # Implement with retry
        result = await implement_with_retry(batch)

        if result['success']:
            # Deploy
            deploy_result = await deploy_changes(result, batch)

            if deploy_result['success']:
                await update_batch_status(batch_id, 'deployed', {
                    'commit_sha': deploy_result['commit_sha'],
                    'pr_url': deploy_result['pr_url']
                })
                print(f"✅ Batch deployed: {deploy_result['pr_url']}")
            else:
                await update_batch_status(batch_id, 'deploy_failed', {
                    'error': deploy_result['error']
                })
                print(f"❌ Deploy failed: {deploy_result['error']}")
        else:
            # Escalate to human review
            await update_batch_status(batch_id, 'needs_review', {
                'error': result['error'],
                'attempts': result['attempts']
            })
            await notify_team_for_review(batch_id, result)
            print(f"⚠️ Batch needs human review: {result['error']}")

    print(f"[{datetime.now()}] Pipeline complete.")


# Entry point
if __name__ == '__main__':
    asyncio.run(run_iteration_pipeline())
```

### 4.2 Scheduler

```python
# orchestrator/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

def setup_scheduler():
    """Configure the iteration pipeline scheduler."""

    scheduler = AsyncIOScheduler()

    # Run every hour during business hours
    scheduler.add_job(
        run_iteration_pipeline,
        CronTrigger(hour='8-20', minute=0),  # Every hour 8am-8pm
        id='hourly_iteration',
        name='Hourly Feedback Processing'
    )

    # Run full analysis nightly
    scheduler.add_job(
        run_full_analysis,
        CronTrigger(hour=2, minute=0),  # 2am daily
        id='nightly_analysis',
        name='Nightly Deep Analysis'
    )

    # Monitor deployments every 30 minutes
    scheduler.add_job(
        monitor_recent_deployments,
        CronTrigger(minute='*/30'),
        id='deployment_monitor',
        name='Deployment Health Monitor'
    )

    scheduler.start()
    return scheduler
```

---

## 5. Configuration

### 5.1 Environment Variables

```bash
# .env

# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJhbGc...

# GitHub
GITHUB_TOKEN=ghp_...
GITHUB_REPO=your-org/frepi-agent

# Pipeline Configuration
ITERATION_ENABLED=true
MAX_BATCH_SIZE=5
MAX_RETRY_ATTEMPTS=3
AUTO_DEPLOY_ENABLED=false  # Set to true for full automation

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
NOTIFY_ON_FAILURE=true
NOTIFY_ON_SUCCESS=false
```

### 5.2 Pipeline Configuration

```yaml
# config/iteration_config.yaml

feedback:
  sources:
    - type: rating
      enabled: true
      weight: 1.0
    - type: conversation_signal
      enabled: true
      weight: 0.8
    - type: error_log
      enabled: true
      weight: 1.2

analysis:
  model: claude-sonnet-4-20250514
  confidence_threshold: 0.7
  batch_max_items: 5

implementation:
  model: claude-sonnet-4-20250514
  max_retries: 3
  allowed_tools:
    - Read
    - Edit
    - Write
    - Glob
    - Grep
    - Bash

testing:
  require_tests: true
  min_coverage: 80
  run_integration_tests: true

deployment:
  auto_merge: false  # Require manual approval
  environments:
    - staging
    - production
  rollback_threshold:
    error_rate_increase: 50  # percent
    satisfaction_decrease: 0.5  # points

monitoring:
  duration_hours: 24
  check_interval_minutes: 30
```

---

## 6. Safety Guardrails

### 6.1 Change Limits

```python
# guardrails/limits.py

GUARDRAILS = {
    # Maximum changes per batch
    'max_files_per_batch': 5,
    'max_lines_changed_per_file': 100,
    'max_new_files_per_batch': 2,

    # Protected files (require human review)
    'protected_files': [
        'frepi_agent/config.py',
        'frepi_agent/main.py',
        '.env*',
        'requirements.txt',
    ],

    # Forbidden operations
    'forbidden_patterns': [
        r'DROP TABLE',
        r'DELETE FROM.*WHERE 1=1',
        r'rm -rf',
        r'subprocess\.call.*shell=True',
    ],

    # Deployment limits
    'max_deployments_per_hour': 3,
    'min_time_between_deploys_minutes': 20,

    # Rollback triggers
    'auto_rollback_triggers': {
        'error_rate_increase_percent': 100,
        'response_time_increase_percent': 200,
        'user_complaints_spike': 10,  # per hour
    }
}
```

### 6.2 Human Review Triggers

```python
# guardrails/review_triggers.py

def requires_human_review(changes: dict, batch: dict) -> tuple[bool, str]:
    """
    Determine if changes require human review before deployment.

    Returns:
        (requires_review: bool, reason: str)
    """

    # Check protected files
    for file in changes['files_modified']:
        if any(fnmatch(file, pattern) for pattern in GUARDRAILS['protected_files']):
            return True, f"Protected file modified: {file}"

    # Check change size
    total_lines = sum(changes.get('lines_changed', {}).values())
    if total_lines > 200:
        return True, f"Large change: {total_lines} lines modified"

    # Check for security patterns
    for file, content in changes.get('file_contents', {}).items():
        for pattern in GUARDRAILS['forbidden_patterns']:
            if re.search(pattern, content):
                return True, f"Forbidden pattern detected in {file}"

    # Check batch severity
    if batch.get('severity') == 'CRITICAL':
        return True, "Critical severity requires human review"

    # Check deployment frequency
    recent_deploys = await get_deployments_last_hour()
    if len(recent_deploys) >= GUARDRAILS['max_deployments_per_hour']:
        return True, "Deployment rate limit reached"

    return False, ""
```

---

## 7. Dashboard & Visibility

### 7.1 Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| Feedback → Deployment Time | Time from feedback to production | <4 hours |
| Test Pass Rate | % of automated changes that pass tests | >80% |
| Rollback Rate | % of deployments that get rolled back | <5% |
| User Satisfaction Delta | Change in satisfaction after fixes | >+0.1 |
| Feedback Recurrence | Same issue reported again after fix | <10% |

### 7.2 Slack Notifications

```python
# notifications/slack.py

async def notify_deployment(batch: dict, result: dict):
    """Send Slack notification about deployment."""

    color = '#36a64f' if result['success'] else '#ff0000'

    payload = {
        'attachments': [{
            'color': color,
            'title': f"{'✅' if result['success'] else '❌'} Feedback Implementation",
            'fields': [
                {
                    'title': 'Theme',
                    'value': batch['common_theme'],
                    'short': True
                },
                {
                    'title': 'Items Addressed',
                    'value': str(len(batch['feedback_ids'])),
                    'short': True
                },
                {
                    'title': 'Status',
                    'value': 'Deployed' if result['success'] else 'Failed',
                    'short': True
                },
                {
                    'title': 'PR',
                    'value': result.get('pr_url', 'N/A'),
                    'short': True
                }
            ],
            'footer': 'Frepi Iteration Engine',
            'ts': int(datetime.now().timestamp())
        }]
    }

    await send_slack_message(payload)
```

---

## 8. Getting Started

### 8.1 Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Initialize database tables
python scripts/init_feedback_tables.py

# 4. Run initial test
python -m pytest tests/ -v
```

### 8.2 Manual Trigger

```bash
# Process pending feedback manually
python -m orchestrator.pipeline

# Analyze specific feedback
python -m analyzer.feedback_analyzer --feedback-id <id>

# Deploy specific batch
python -m deployer.github_deployer --batch-id <id>
```

### 8.3 Enable Automation

```bash
# Start the scheduler
python -m orchestrator.scheduler

# Or run as systemd service
sudo systemctl start frepi-iteration
```

---

## 9. Future Enhancements

1. **A/B Testing Integration**
   - Deploy changes to subset of users first
   - Compare metrics before full rollout

2. **Predictive Analysis**
   - Predict issues before users report them
   - Proactive improvements based on patterns

3. **Multi-Model Support**
   - Use different models for different tasks
   - Optimize cost vs quality

4. **Visual Feedback**
   - Screen recording analysis
   - UI/UX improvement suggestions

5. **Cross-Repository Changes**
   - Coordinate changes across frontend/backend
   - Synchronized deployments

---

*Document Version: 1.0*
*Last Updated: January 2026*
