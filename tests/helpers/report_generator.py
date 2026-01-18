"""Test report generation for Frepi Agent tests."""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class TestResult:
    """Result of a single test case."""
    test_id: str
    test_name: str
    group: str
    passed: bool
    duration_ms: float
    turns_tested: int
    assertions_passed: int
    assertions_failed: int
    failure_details: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


@dataclass
class TestReport:
    """Complete test report."""
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float
    groups_summary: dict
    results: list[TestResult] = field(default_factory=list)


class ReportGenerator:
    """Generates test reports in JSON and HTML formats."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(__file__).parent.parent / "reports"
        self.output_dir.mkdir(exist_ok=True)

    def generate_json_report(self, report: TestReport) -> Path:
        """Generate JSON report."""
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w") as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False)

        return filepath

    def generate_html_report(self, report: TestReport) -> Path:
        """Generate HTML report."""
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = self.output_dir / filename

        html_content = self._render_html(report)

        with open(filepath, "w") as f:
            f.write(html_content)

        return filepath

    def _render_html(self, report: TestReport) -> str:
        """Render HTML report content."""
        pass_rate = (report.passed / report.total_tests * 100) if report.total_tests > 0 else 0

        # Group results by group
        groups_html = ""
        for group_id, summary in report.groups_summary.items():
            group_results = [r for r in report.results if r.group == group_id]
            groups_html += self._render_group_section(group_id, summary, group_results)

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Frepi Agent Test Report - {report.timestamp}</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}
        .header .meta {{
            opacity: 0.9;
            font-size: 14px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
        }}
        .stat-card.passed {{
            border-left: 4px solid #28a745;
        }}
        .stat-card.failed {{
            border-left: 4px solid #dc3545;
        }}
        .stat-card.total {{
            border-left: 4px solid #6c757d;
        }}
        .stat-card.rate {{
            border-left: 4px solid #667eea;
        }}
        .stat-value {{
            font-size: 48px;
            font-weight: 700;
            color: #333;
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 5px;
        }}
        .group {{
            background: white;
            margin-bottom: 20px;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .group-header {{
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .group-header h3 {{
            font-size: 18px;
            color: #333;
        }}
        .group-stats {{
            font-size: 14px;
            color: #666;
        }}
        .test-row {{
            padding: 15px 20px;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .test-row:last-child {{
            border-bottom: none;
        }}
        .test-row.passed {{
            border-left: 3px solid #28a745;
        }}
        .test-row.failed {{
            border-left: 3px solid #dc3545;
            background: #fff5f5;
        }}
        .test-id {{
            font-family: monospace;
            font-weight: 600;
            color: #667eea;
            min-width: 60px;
        }}
        .test-name {{
            flex: 1;
            font-weight: 500;
        }}
        .badge {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-pass {{
            background: #d4edda;
            color: #155724;
        }}
        .badge-fail {{
            background: #f8d7da;
            color: #721c24;
        }}
        .test-meta {{
            font-size: 12px;
            color: #999;
        }}
        .details {{
            margin-top: 10px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            font-family: monospace;
            font-size: 12px;
            white-space: pre-wrap;
            color: #dc3545;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Frepi Agent Test Report</h1>
            <div class="meta">
                <div>Generated: {report.timestamp}</div>
                <div>Duration: {report.duration_seconds:.2f}s</div>
            </div>
        </div>

        <div class="summary">
            <div class="stat-card total">
                <div class="stat-value">{report.total_tests}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat-card passed">
                <div class="stat-value">{report.passed}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat-card failed">
                <div class="stat-value">{report.failed}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card rate">
                <div class="stat-value">{pass_rate:.0f}%</div>
                <div class="stat-label">Pass Rate</div>
            </div>
        </div>

        {groups_html}

        <div class="footer">
            Frepi Agent Test Framework v1.0
        </div>
    </div>
</body>
</html>"""

    def _render_group_section(self, group_id: str, summary: dict, results: list) -> str:
        """Render a single group section."""
        group_names = {
            "A": "Onboarding",
            "B": "Pre-Purchase",
            "C": "Core Purchasing",
            "D": "Post-Purchase",
            "E": "Management",
            "F": "Error Handling",
        }

        group_name = group_names.get(group_id, f"Group {group_id}")
        passed = summary.get("passed", 0)
        total = summary.get("total", 0)

        results_html = ""
        for r in results:
            status_class = "passed" if r.passed else "failed"
            badge_class = "badge-pass" if r.passed else "badge-fail"
            badge_text = "PASS" if r.passed else "FAIL"

            details = ""
            if not r.passed and r.failure_details:
                details = f'<div class="details">{chr(10).join(r.failure_details)}</div>'

            results_html += f"""
            <div class="test-row {status_class}">
                <span class="test-id">{r.test_id}</span>
                <span class="test-name">{r.test_name}</span>
                <span class="test-meta">{r.turns_tested} turns | {r.duration_ms:.0f}ms</span>
                <span class="badge {badge_class}">{badge_text}</span>
            </div>
            {details}
"""

        return f"""
        <div class="group">
            <div class="group-header">
                <h3>Group {group_id}: {group_name}</h3>
                <span class="group-stats">{passed}/{total} passed</span>
            </div>
            {results_html}
        </div>
"""


def create_report_from_pytest_results(pytest_results: list[dict]) -> TestReport:
    """
    Create a TestReport from pytest results.

    Args:
        pytest_results: List of result dicts with keys:
            - nodeid: Test node ID
            - passed: Boolean
            - duration: Float in seconds
            - details: Optional list of failure messages

    Returns:
        TestReport object
    """
    results = []
    groups_summary = {}

    for pr in pytest_results:
        # Parse test ID from nodeid (e.g., "test_agent.py::TestAgentFromMatrix::test_from_matrix[A001-First_greeting]")
        nodeid = pr.get("nodeid", "")
        test_id = "unknown"
        test_name = "unknown"

        if "[" in nodeid and "]" in nodeid:
            param = nodeid.split("[")[1].rstrip("]")
            if "-" in param:
                test_id = param.split("-")[0]
                test_name = param.split("-", 1)[1].replace("_", " ")

        # Determine group from test_id
        group = test_id[0] if test_id and test_id[0].isalpha() else "X"

        result = TestResult(
            test_id=test_id,
            test_name=test_name,
            group=group,
            passed=pr.get("passed", False),
            duration_ms=pr.get("duration", 0) * 1000,
            turns_tested=pr.get("turns", 1),
            assertions_passed=pr.get("assertions_passed", 0),
            assertions_failed=pr.get("assertions_failed", 0),
            failure_details=pr.get("details", []),
            tool_calls=pr.get("tool_calls", []),
        )
        results.append(result)

        # Update group summary
        if group not in groups_summary:
            groups_summary[group] = {"total": 0, "passed": 0, "failed": 0}
        groups_summary[group]["total"] += 1
        if result.passed:
            groups_summary[group]["passed"] += 1
        else:
            groups_summary[group]["failed"] += 1

    total_passed = sum(1 for r in results if r.passed)
    total_failed = sum(1 for r in results if not r.passed)
    total_duration = sum(r.duration_ms for r in results) / 1000

    return TestReport(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_tests=len(results),
        passed=total_passed,
        failed=total_failed,
        skipped=0,
        duration_seconds=total_duration,
        groups_summary=groups_summary,
        results=results,
    )
