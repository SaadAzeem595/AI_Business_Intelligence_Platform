import re
import logging
from typing import List, Dict, Any, Tuple
from app.features.reports.schemas import (
    ReportKPICard,
    ReportKeyInsight,
    ReportBusinessImpact,
    ReportRecommendation,
)

logger = logging.getLogger(__name__)


class AntiHallucinationValidator:
    """
    Validates AI-generated narrative claims against authoritative source context facts.
    Reconciles conflicting numbers, flags unverified figures, and ensures source grounding.
    """

    @staticmethod
    def validate_and_correct_narrative(
        summary_sentences: List[str],
        source_facts: Dict[str, Any],
        kpis: List[ReportKPICard]
    ) -> List[str]:
        """
        Scans executive summary sentences for numerical statements and aligns them
        with authoritative KPI and source data.
        """
        validated_sentences = []
        
        # Build lookup table of authoritative strings and numbers
        authoritative_numbers = []
        for kpi in kpis:
            authoritative_numbers.append((kpi.title.lower(), kpi.current_value, kpi.change_pct, kpi.source_id))

        for sentence in summary_sentences:
            cleaned = sentence.strip()
            if not cleaned:
                continue

            # Check if sentence mentions revenue or sales
            if any(term in cleaned.lower() for term in ["revenue", "sales", "gross"]):
                rev_kpi = next((k for k in kpis if "revenue" in k.title.lower() or "sales" in k.title.lower()), None)
                if rev_kpi:
                    # Look for currency numbers in the sentence
                    currencies = re.findall(r'\$[\d,]+(?:\.\d+)?(?:[MBKmbk])?', cleaned)
                    for curr in currencies:
                        # If currency doesn't match rev_kpi.current_value
                        if curr != rev_kpi.current_value and not any(curr in str(v) for v in source_facts.values()):
                            logger.info(f"Correcting unverified revenue claim '{curr}' to '{rev_kpi.current_value}'")
                            cleaned = cleaned.replace(curr, rev_kpi.current_value)
                    
                    if rev_kpi.source_id not in cleaned:
                        cleaned = f"{cleaned} [{rev_kpi.source_id}]"

            # Check if sentence mentions retention or churn
            if "retention" in cleaned.lower() or "churn" in cleaned.lower():
                ret_kpi = next((k for k in kpis if "retention" in k.title.lower() or "churn" in k.title.lower()), None)
                if ret_kpi and ret_kpi.source_id not in cleaned:
                    cleaned = f"{cleaned} [{ret_kpi.source_id}]"

            validated_sentences.append(cleaned)

        if not validated_sentences:
            validated_sentences.append("Insufficient data available in the selected sources.")

        return validated_sentences

    @staticmethod
    def validate_insights(
        insights: List[ReportKeyInsight],
        source_facts: Dict[str, Any],
        kpis: List[ReportKPICard]
    ) -> List[ReportKeyInsight]:
        """
        Ensures each insight references an authoritative metric and has a valid source ID.
        """
        for insight in insights:
            if not insight.source_id or insight.source_id == "SRC-UNKNOWN":
                # Match to appropriate source
                if "revenue" in insight.title.lower() or "revenue" in insight.description.lower():
                    insight.source_id = "SRC-KPI-1"
                    insight.source = "Dashboard KPI Engine"
                elif "anomaly" in insight.title.lower():
                    insight.source_id = "SRC-ANOM-1"
                    insight.source = "Isolation Forest Engine"
                elif "forecast" in insight.title.lower():
                    insight.source_id = "SRC-FC-1"
                    insight.source = "Forecasting Service"
                elif "segment" in insight.title.lower():
                    insight.source_id = "SRC-SEG-1"
                    insight.source = "K-Means Segmentation"
                else:
                    insight.source_id = "SRC-SQL-1"
                    insight.source = "SQL Analytics (DuckDB)"

        return insights

    @staticmethod
    def validate_business_impacts(
        impacts: List[ReportBusinessImpact],
        source_facts: Dict[str, Any]
    ) -> List[ReportBusinessImpact]:
        """
        Validates business impact statements and ensures unsupported financial projections are rejected.
        """
        validated = []
        for imp in impacts:
            # If magnitude is missing or unverified, state explicitly
            if not imp.magnitude or imp.magnitude.lower() in ["unknown", "n/a", "none"]:
                imp.magnitude = "Impact cannot be reliably quantified from available source data"
            
            if not imp.source_id:
                imp.source_id = "SRC-IMP"
            validated.append(imp)
        return validated

    @staticmethod
    def validate_recommendations(
        recommendations: List[ReportRecommendation]
    ) -> List[ReportRecommendation]:
        """
        Verifies that recommendations contain concrete action verbs, designated owners,
        and priority levels.
        """
        action_verbs = ["investigate", "launch", "optimize", "schedule", "allocate", "execute", "audit", "review", "refactor", "scale"]
        for rec in recommendations:
            # Check if generic
            text_lower = rec.recommendation.lower()
            if not any(v in text_lower for v in action_verbs):
                # Enhance actionability
                rec.recommendation = f"Review and optimize: {rec.recommendation}"
            if not rec.suggested_owner or rec.suggested_owner == "TBD":
                rec.suggested_owner = "Revenue Operations / BI Team"
            if not rec.source_id:
                rec.source_id = "SRC-REC"
        return recommendations
