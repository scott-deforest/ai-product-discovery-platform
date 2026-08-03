"""Prompt contract for evidence-grounded opportunity generation."""

from src.models import EvidencePack


PROMPT_VERSION = "opportunity-analysis-v1"

SYSTEM_PROMPT = """You are an AI product discovery analyst.

Identify one to three practical AI opportunities from the supplied assessment
evidence. Your output will support a human decision; it is not an autonomous
recommendation.

Rules:
- Use only the supplied evidence and assessment context.
- Cite one or more supplied citation IDs for every opportunity.
- Never invent a citation ID, fact, metric, system, requirement, or ROI estimate.
- State uncertain assumptions and important evidence gaps under missing_information.
- Prefer narrow, testable capabilities over broad transformation proposals.
- Include meaningful risks, safeguards, human oversight, and measurable success signals.
- Score each rubric component from 1 to 5 and explain the score in plain language.
- A low evidence-strength score is appropriate when the source material is limited.
- Do not treat retrieval similarity as confidence or proof.
"""


def build_analysis_prompt(
    assessment_name: str,
    assessment_description: str,
    evidence_pack: EvidencePack,
) -> str:
    """Render assessment context and stable evidence IDs for the model."""
    description = assessment_description.strip() or "No description provided."
    evidence_sections = []
    for item in evidence_pack.items:
        dimensions = ", ".join(dimension.value for dimension in item.dimensions)
        evidence_sections.append(
            "\n".join(
                [
                    f"[{item.citation_id}]",
                    f"Source: {item.filename}, chunk {item.chunk_index + 1}",
                    f"Evidence dimensions: {dimensions}",
                    item.content,
                ]
            )
        )

    evidence_text = "\n\n".join(evidence_sections)
    return f"""Assessment: {assessment_name.strip()}
Assessment description: {description}

Create a concise executive summary and one to three distinct AI opportunities.
Use the structured response schema exactly.

SOURCE EVIDENCE
{evidence_text}
"""
