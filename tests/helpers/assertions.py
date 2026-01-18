"""Custom assertion helpers for Frepi Agent tests."""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class AssertionResult:
    """Result of an assertion check."""
    passed: bool
    message: str
    details: Optional[dict] = None


class FrepiAssertions:
    """Custom assertions for Frepi agent responses."""

    # Portuguese language markers
    PT_BR_MARKERS = [
        "você", "não", "está", "são", "pode", "quer",
        "obrigado", "olá", "bem-vindo", "preciso", "quero",
        "fazer", "compra", "preço", "fornecedor", "produto"
    ]

    # Menu emojis
    MENU_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]

    # Common emojis used in responses
    RESPONSE_EMOJIS = [
        "✅", "⚠️", "❌", "🎯", "💰", "📦",
        "🥩", "🍚", "🫒", "👋", "🛒", "📋"
    ]

    # Brazilian price format pattern: R$ 1.234,56
    PRICE_PATTERN = r"R\$\s*[\d.,]+(?:,\d{2})?"

    @classmethod
    def assert_contains_any(cls, response: str, terms: list[str]) -> AssertionResult:
        """Check if response contains at least one of the terms."""
        response_lower = response.lower()
        found = [t for t in terms if t.lower() in response_lower]

        if found:
            return AssertionResult(
                passed=True,
                message=f"Found terms: {found}",
                details={"found": found}
            )
        return AssertionResult(
            passed=False,
            message=f"None of the expected terms found. Expected one of: {terms}",
            details={"expected": terms}
        )

    @classmethod
    def assert_contains_all(cls, response: str, terms: list[str]) -> AssertionResult:
        """Check if response contains all of the terms."""
        missing = [t for t in terms if t not in response]

        if not missing:
            return AssertionResult(
                passed=True,
                message="All expected terms found"
            )
        return AssertionResult(
            passed=False,
            message=f"Missing terms: {missing}",
            details={"missing": missing}
        )

    @classmethod
    def assert_not_contains(cls, response: str, terms: list[str]) -> AssertionResult:
        """Check that response does not contain any of the forbidden terms."""
        response_lower = response.lower()
        found = [t for t in terms if t.lower() in response_lower]

        if not found:
            return AssertionResult(
                passed=True,
                message="No forbidden terms found"
            )
        return AssertionResult(
            passed=False,
            message=f"Found forbidden terms: {found}",
            details={"found": found}
        )

    @classmethod
    def assert_menu_displayed(cls, response: str) -> AssertionResult:
        """Check if the 4-option menu is displayed."""
        missing_emojis = [e for e in cls.MENU_EMOJIS if e not in response]

        if not missing_emojis:
            return AssertionResult(
                passed=True,
                message="Menu with all 4 options displayed"
            )
        return AssertionResult(
            passed=False,
            message=f"Menu incomplete. Missing: {missing_emojis}",
            details={"missing": missing_emojis}
        )

    @classmethod
    def assert_has_emojis(cls, response: str) -> AssertionResult:
        """Check if response contains emojis."""
        found_emojis = [e for e in cls.RESPONSE_EMOJIS + cls.MENU_EMOJIS if e in response]

        if found_emojis:
            return AssertionResult(
                passed=True,
                message=f"Found emojis: {found_emojis}",
                details={"found": found_emojis}
            )
        return AssertionResult(
            passed=False,
            message="No emojis found in response"
        )

    @classmethod
    def assert_portuguese_language(cls, response: str) -> AssertionResult:
        """Check if response is in Portuguese."""
        response_lower = response.lower()
        found_markers = [m for m in cls.PT_BR_MARKERS if m in response_lower]

        # Consider Portuguese if at least 2 markers found or response is short
        if len(found_markers) >= 2 or len(response) < 50:
            return AssertionResult(
                passed=True,
                message=f"Portuguese language detected. Markers: {found_markers}",
                details={"markers": found_markers}
            )
        return AssertionResult(
            passed=False,
            message=f"Portuguese language not confidently detected. Found: {found_markers}",
            details={"markers": found_markers}
        )

    @classmethod
    def assert_price_format(cls, response: str) -> AssertionResult:
        """Check if response contains Brazilian price format."""
        prices = re.findall(cls.PRICE_PATTERN, response)

        if prices:
            return AssertionResult(
                passed=True,
                message=f"Found prices: {prices}",
                details={"prices": prices}
            )
        return AssertionResult(
            passed=False,
            message="No Brazilian price format (R$ X.XXX,XX) found"
        )

    @classmethod
    def assert_has_supplier_names(cls, response: str) -> AssertionResult:
        """Check if response contains specific supplier names (not generic terms)."""
        # Generic terms that should NOT be used
        generic_terms = [
            "os fornecedores",
            "alguns fornecedores",
            "fornecedores disponíveis",
            "vários fornecedores"
        ]

        response_lower = response.lower()
        found_generic = [t for t in generic_terms if t in response_lower]

        if found_generic:
            return AssertionResult(
                passed=False,
                message=f"Found generic supplier references: {found_generic}",
                details={"generic_found": found_generic}
            )

        return AssertionResult(
            passed=True,
            message="No generic supplier terms found"
        )

    @classmethod
    def assert_tool_calls(
        cls,
        recorded_calls: list[dict],
        expected_calls: list[dict],
        forbidden_calls: list[str] = None
    ) -> AssertionResult:
        """
        Validate tool calls made during the test.

        Args:
            recorded_calls: List of {"name": str, "args": dict} from tracker
            expected_calls: List of expected tool calls with optional arg checks
            forbidden_calls: List of tool names that should NOT be called
        """
        recorded_names = [c["name"] for c in recorded_calls]

        # Check forbidden calls
        if forbidden_calls:
            found_forbidden = [n for n in forbidden_calls if n in recorded_names]
            if found_forbidden:
                return AssertionResult(
                    passed=False,
                    message=f"Forbidden tools were called: {found_forbidden}",
                    details={"forbidden": found_forbidden}
                )

        # Check expected calls
        missing_calls = []
        for expected in expected_calls:
            expected_name = expected.get("name")
            if expected_name not in recorded_names:
                missing_calls.append(expected_name)
                continue

            # Check args if specified
            args_to_check = expected.get("args_contain", {})
            if args_to_check:
                matching_calls = [c for c in recorded_calls if c["name"] == expected_name]
                args_matched = False
                for call in matching_calls:
                    call_args = call.get("args", {})
                    if all(
                        k in call_args and str(args_to_check[k]).lower() in str(call_args[k]).lower()
                        for k in args_to_check
                    ):
                        args_matched = True
                        break

                if not args_matched:
                    missing_calls.append(f"{expected_name}(with args: {args_to_check})")

        if missing_calls:
            return AssertionResult(
                passed=False,
                message=f"Expected tool calls missing: {missing_calls}",
                details={
                    "missing": missing_calls,
                    "recorded": recorded_names
                }
            )

        return AssertionResult(
            passed=True,
            message=f"All expected tool calls made: {recorded_names}",
            details={"recorded": recorded_calls}
        )

    @classmethod
    def assert_no_error(cls, response: str) -> AssertionResult:
        """Check that response doesn't contain error indicators."""
        error_patterns = [
            r"erro\s+interno",
            r"error",
            r"exception",
            r"falha\s+no\s+sistema",
            r"não\s+foi\s+possível\s+processar",
            r"traceback",
            r"stack\s+trace"
        ]

        response_lower = response.lower()
        for pattern in error_patterns:
            if re.search(pattern, response_lower):
                return AssertionResult(
                    passed=False,
                    message=f"Error pattern detected: {pattern}",
                    details={"pattern": pattern}
                )

        return AssertionResult(
            passed=True,
            message="No error patterns detected"
        )
