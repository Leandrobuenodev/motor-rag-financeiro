"""Versioned manual regression cases for the Banco do Brasil 1Q26 report.

Expected facts are test data only; application code never branches on these values.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationCase:
    question: str
    expected_fact: str
    retrieval_terms: tuple[str, ...]


CASES = (
    EvaluationCase(
        "Qual foi o lucro líquido ajustado no 1T26?", "3.431", ("lucro", "ajustado")
    ),
    EvaluationCase(
        "What was the adjusted net income in 1Q26?", "3.431", ("lucro", "ajustado")
    ),
    EvaluationCase(
        "Qual foi a inadimplência acima de 90 dias em março de 2026?",
        "5.05", ("inad", "90d")
    ),
    EvaluationCase(
        "What was the 90-day delinquency ratio in March 2026?", "5.05", ("inad", "90d")
    ),
    EvaluationCase(
        "Qual foi o Índice de Basileia em março de 2026?", "14.23", ("basileia",)
    ),
    EvaluationCase(
        "What was the Basel ratio in March 2026?", "14.23", ("basileia",)
    ),
    EvaluationCase(
        "Qual foi a Margem Financeira Bruta no 1T26?",
        "27.426", ("margem", "financeira")
    ),
    EvaluationCase(
        "What was the gross financial margin in 1Q26?",
        "27.426", ("margem", "financeira")
    ),
    EvaluationCase(
        "Qual era a Carteira de Crédito Expandida em março de 2026?",
        "1.305.528", ("carteira", "expandida")
    ),
)
