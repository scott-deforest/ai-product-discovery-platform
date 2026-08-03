"""Tests for assessment readiness rules."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from src.assessment_runner import (
    EVIDENCE_QUERIES,
    build_evidence_pack,
    check_assessment_readiness,
    generate_opportunity_analysis,
    start_assessment_run,
)
from src.database import (
    create_assessment,
    create_document,
    get_assessment_run,
    initialize_database,
    list_document_chunks,
    replace_document_chunks,
)
from src.models import (
    AssessmentDimension,
    EvidenceItem,
    EvidencePack,
    OpportunityAnalysis,
    RunStatus,
)
from src.prompts.opportunity_analysis import SYSTEM_PROMPT
from src.vector_store import get_collection


class AssessmentReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "test.db"
        self.collection = get_collection(self.root / "chroma")
        initialize_database(self.database_path)
        self.assessment_id = create_assessment(
            "Customer Support Workflow",
            database_path=self.database_path,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_empty_assessment_is_not_ready(self) -> None:
        readiness = check_assessment_readiness(
            self.assessment_id,
            self.database_path,
            self.collection,
        )

        self.assertFalse(readiness.ready)
        self.assertEqual(readiness.document_count, 0)
        self.assertIn("needs at least one document", readiness.reasons[0])

        with self.assertRaisesRegex(ValueError, "Assessment is not ready"):
            start_assessment_run(
                self.assessment_id,
                "test-model",
                "v1",
                self.database_path,
                self.collection,
            )

    def test_all_current_chunks_must_be_indexed(self) -> None:
        create_document(
            document_id="document-1",
            assessment_id=self.assessment_id,
            filename="workflow.md",
            stored_path="/tmp/workflow.md",
            file_type="md",
            size_bytes=42,
            database_path=self.database_path,
        )
        replace_document_chunks(
            document_id="document-1",
            assessment_id=self.assessment_id,
            chunks=["First support chunk.", "Second support chunk."],
            database_path=self.database_path,
        )
        chunks = list_document_chunks("document-1", self.database_path)
        self.collection.upsert(
            ids=[str(chunk["id"]) for chunk in chunks],
            embeddings=[[1.0, 0.0], [0.9, 0.1]],
            documents=[str(chunk["content"]) for chunk in chunks],
            metadatas=[
                {
                    "assessment_id": self.assessment_id,
                    "document_id": "document-1",
                }
                for _ in chunks
            ],
        )

        readiness = check_assessment_readiness(
            self.assessment_id,
            self.database_path,
            self.collection,
        )

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.chunk_count, 2)
        self.assertEqual(readiness.indexed_chunk_count, 2)

        run_id = start_assessment_run(
            self.assessment_id,
            "test-model",
            "v1",
            self.database_path,
            self.collection,
        )
        run = get_assessment_run(run_id, self.database_path)

        self.assertEqual(run["status"], RunStatus.RUNNING.value)
        self.assertIsNotNone(run["started_at"])

    def test_evidence_pack_deduplicates_chunks_across_dimensions(self) -> None:
        create_document(
            document_id="document-1",
            assessment_id=self.assessment_id,
            filename="workflow.md",
            stored_path="/tmp/workflow.md",
            file_type="md",
            size_bytes=42,
            database_path=self.database_path,
        )
        replace_document_chunks(
            document_id="document-1",
            assessment_id=self.assessment_id,
            chunks=["Specialists repeatedly search several systems."],
            database_path=self.database_path,
        )
        chunk = list_document_chunks("document-1", self.database_path)[0]
        self.collection.upsert(
            ids=[str(chunk["id"])],
            embeddings=[[1.0, 0.0]],
            documents=[str(chunk["content"])],
            metadatas=[
                {
                    "assessment_id": self.assessment_id,
                    "document_id": "document-1",
                    "filename": "workflow.md",
                    "chunk_index": 0,
                }
            ],
        )

        search_calls = []

        def fake_search(**kwargs):
            search_calls.append(kwargs)
            return [
                {
                    "chunk_id": str(chunk["id"]),
                    "content": str(chunk["content"]),
                    "metadata": {
                        "assessment_id": self.assessment_id,
                        "document_id": "document-1",
                        "filename": "workflow.md",
                        "chunk_index": 0,
                    },
                    "distance": 0.2,
                    "similarity": 0.8,
                }
            ]

        evidence_pack = build_evidence_pack(
            self.assessment_id,
            self.database_path,
            self.collection,
            search_fn=fake_search,
        )

        self.assertEqual(len(search_calls), len(EVIDENCE_QUERIES))
        self.assertTrue(
            all(call["assessment_id"] == self.assessment_id for call in search_calls)
        )
        self.assertEqual(len(evidence_pack.items), 1)
        self.assertEqual(evidence_pack.items[0].citation_id, "E1")
        self.assertEqual(
            len(evidence_pack.items[0].dimensions),
            len(EVIDENCE_QUERIES),
        )


class OpportunityGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence_pack = EvidencePack(
            assessment_id="assessment-1",
            items=[
                EvidenceItem(
                    citation_id="E1",
                    chunk_id="chunk-1",
                    document_id="document-1",
                    filename="workflow.md",
                    chunk_index=0,
                    content="Specialists repeatedly search several systems.",
                    dimensions=[AssessmentDimension.WORKFLOW_PAIN_POINTS],
                    similarity=0.82,
                )
            ],
        )

    @staticmethod
    def analysis(citation_id: str = "E1") -> OpportunityAnalysis:
        score = {"score": 4, "rationale": "Supported by the supplied evidence."}
        return OpportunityAnalysis.model_validate(
            {
                "executive_summary": "The workflow has a focused retrieval opportunity.",
                "opportunities": [
                    {
                        "title": "Knowledge retrieval assistant",
                        "summary": "Help specialists find relevant knowledge faster.",
                        "problem": "Specialists repeatedly search several systems.",
                        "proposed_capability": "Cited semantic knowledge retrieval.",
                        "primary_users": ["Support specialists"],
                        "workflow_placement": "Issue research",
                        "expected_value": "Reduce repeated searches.",
                        "data_requirements": ["Approved knowledge sources"],
                        "risks": ["Outdated source material"],
                        "safeguards": ["Show citations", "Human review"],
                        "success_metrics": ["Median research time"],
                        "missing_information": ["Current research-time baseline"],
                        "business_value": score,
                        "feasibility": score,
                        "evidence_strength": score,
                        "risk_readiness": score,
                        "citation_ids": [citation_id],
                    }
                ],
            }
        )

    def test_generation_uses_structured_output_and_attaches_trusted_evidence(
        self,
    ) -> None:
        parse_calls = []

        class FakeResponses:
            def parse(inner_self, **kwargs):
                parse_calls.append(kwargs)
                return SimpleNamespace(
                    id="response-1",
                    output_parsed=self.analysis(),
                )

        fake_client = SimpleNamespace(responses=FakeResponses())
        result = generate_opportunity_analysis(
            evidence_pack=self.evidence_pack,
            assessment_name="Customer Support Workflow",
            assessment_description="Review the current workflow.",
            openai_client=fake_client,
            model="test-model",
        )

        self.assertEqual(parse_calls[0]["model"], "test-model")
        self.assertEqual(parse_calls[0]["text_format"], OpportunityAnalysis)
        self.assertEqual(parse_calls[0]["input"][0]["content"], SYSTEM_PROMPT)
        self.assertIn("[E1]", parse_calls[0]["input"][1]["content"])
        self.assertEqual(result.opportunities[0].citation_ids, ["E1"])
        self.assertEqual(result.evidence[0].chunk_id, "chunk-1")
        self.assertEqual(result.evidence[0].filename, "workflow.md")

    def test_generation_rejects_an_invented_citation(self) -> None:
        fake_client = SimpleNamespace(
            responses=SimpleNamespace(
                parse=lambda **kwargs: SimpleNamespace(
                    id="response-2",
                    output_parsed=self.analysis("UNKNOWN"),
                )
            )
        )

        with self.assertRaisesRegex(ValidationError, "unknown citation"):
            generate_opportunity_analysis(
                self.evidence_pack,
                "Customer Support Workflow",
                openai_client=fake_client,
                model="test-model",
            )

    def test_generation_rejects_an_unparsed_response(self) -> None:
        fake_client = SimpleNamespace(
            responses=SimpleNamespace(
                parse=lambda **kwargs: SimpleNamespace(
                    id="response-3",
                    output_parsed=None,
                )
            )
        )

        with self.assertRaisesRegex(ValueError, "usable structured analysis"):
            generate_opportunity_analysis(
                self.evidence_pack,
                "Customer Support Workflow",
                openai_client=fake_client,
                model="test-model",
            )


if __name__ == "__main__":
    unittest.main()
