"""YAML test case loader for Frepi Agent tests."""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExpectedBehavior:
    """Expected behaviors for a test turn."""
    contains_any: list[str] = field(default_factory=list)
    contains_all: list[str] = field(default_factory=list)
    not_contains: list[str] = field(default_factory=list)
    contains_menu: bool = False
    has_price_format: bool = False
    has_supplier_names: bool = False
    has_emojis: bool = False
    language: str = "pt-BR"


@dataclass
class ToolCallExpectation:
    """Expected tool call."""
    name: str
    args_contain: dict = field(default_factory=dict)


@dataclass
class ConversationTurn:
    """A single turn in a test conversation."""
    turn: int
    user_message: str
    expected: ExpectedBehavior
    tool_calls_expected: list[ToolCallExpectation] = field(default_factory=list)
    tool_calls_forbidden: list[str] = field(default_factory=list)


@dataclass
class TestCase:
    """A complete test case."""
    id: str
    name: str
    group: str
    description: str
    priority: str
    conversation: list[ConversationTurn]
    mock_overrides: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class TestMatrix:
    """Complete test matrix."""
    version: str
    settings: dict
    groups: list[dict]
    test_cases: list[TestCase]


def load_test_matrix(path: Optional[Path] = None) -> TestMatrix:
    """
    Load test matrix from YAML file.

    Args:
        path: Path to YAML file. Defaults to tests/test_matrix.yaml

    Returns:
        TestMatrix object with all test cases
    """
    if path is None:
        path = Path(__file__).parent.parent / "test_matrix.yaml"

    with open(path) as f:
        data = yaml.safe_load(f)

    test_cases = []
    for tc_data in data.get("test_cases", []):
        conversation = []
        for turn_data in tc_data.get("conversation", []):
            expected_data = turn_data.get("expected", {})
            expected = ExpectedBehavior(
                contains_any=expected_data.get("contains_any", []),
                contains_all=expected_data.get("contains_all", []),
                not_contains=expected_data.get("not_contains", []),
                contains_menu=expected_data.get("contains_menu", False),
                has_price_format=expected_data.get("has_price_format", False),
                has_supplier_names=expected_data.get("has_supplier_names", False),
                has_emojis=expected_data.get("has_emojis", False),
                language=expected_data.get("language", "pt-BR"),
            )

            tool_calls = [
                ToolCallExpectation(
                    name=tc.get("name", ""),
                    args_contain=tc.get("args_contain", {}),
                )
                for tc in turn_data.get("tool_calls_expected", [])
            ]

            conversation.append(ConversationTurn(
                turn=turn_data.get("turn", 1),
                user_message=turn_data.get("user_message", ""),
                expected=expected,
                tool_calls_expected=tool_calls,
                tool_calls_forbidden=turn_data.get("tool_calls_forbidden", []),
            ))

        test_cases.append(TestCase(
            id=tc_data.get("id", ""),
            name=tc_data.get("name", ""),
            group=tc_data.get("group", ""),
            description=tc_data.get("description", ""),
            priority=tc_data.get("priority", "medium"),
            conversation=conversation,
            mock_overrides=tc_data.get("mock_overrides", {}),
            tags=tc_data.get("tags", []),
        ))

    return TestMatrix(
        version=data.get("version", "1.0"),
        settings=data.get("settings", {}),
        groups=data.get("groups", []),
        test_cases=test_cases,
    )


def get_test_cases_by_group(matrix: TestMatrix, group_id: str) -> list[TestCase]:
    """Filter test cases by group."""
    return [tc for tc in matrix.test_cases if tc.group == group_id]


def get_test_cases_by_priority(matrix: TestMatrix, priority: str) -> list[TestCase]:
    """Filter test cases by priority."""
    return [tc for tc in matrix.test_cases if tc.priority == priority]


def get_test_case_by_id(matrix: TestMatrix, test_id: str) -> Optional[TestCase]:
    """Get a specific test case by ID."""
    for tc in matrix.test_cases:
        if tc.id == test_id:
            return tc
    return None
