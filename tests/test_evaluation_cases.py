from tests.evaluation_cases import CASES


def test_regression_suite_contains_bilingual_financial_cases() -> None:
    assert len(CASES) == 9
    assert sum(case.question.startswith("What") for case in CASES) == 4
    assert all(case.expected_fact and case.retrieval_terms for case in CASES)
