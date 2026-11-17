"""
Dependency injection container.

Assembles all components at startup; business logic receives only port
interfaces — it has no knowledge of which adapters are active.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..ingestion.service import IngestionService
from ..assessment.service import AssessmentService
from ..decision_engine.risk_scorer import RiskScorer
from ..model_gateway.deterministic import DeterministicModelProvider
from ..model_gateway.gemini import GeminiModelProvider
from ..persistence.knowledge_repository.lexical import LexicalKnowledgeRepository
from ..persistence.message_bus.in_memory import InMemoryMessageBus
from ..persistence.message_bus.pubsub_emulator import PubSubEmulatorMessageBus
from ..persistence.sqlite.assessment_store import SQLiteAssessmentStore
from ..persistence.sqlite.event_store import SQLiteEventStore
from ..retrieval.service import RetrievalService
from ..event_processing.worker import EventProcessingWorker
from ..shared.config import Settings
from ..shared.data_loader import load_synthetic_data
from ..shared.logging import get_logger
from ..shared.ports.message_bus import MessageBusPort
from ..shared.ports.model_provider import ModelProviderPort

logger = get_logger("dependencies")


@dataclass
class Container:
    """
    Assembled dependency graph.

    Concrete adapters live here; services see only port abstractions.
    """

    event_store: SQLiteEventStore
    assessment_store: SQLiteAssessmentStore
    message_bus: MessageBusPort
    knowledge_repo: LexicalKnowledgeRepository
    model_provider: ModelProviderPort
    ingestion_service: IngestionService
    retrieval_service: RetrievalService
    risk_scorer: RiskScorer
    assessment_service: AssessmentService
    worker: EventProcessingWorker

    @classmethod
    async def create(cls, settings: Settings) -> "Container":
        # ── Persistence ───────────────────────────────────────────────────────
        db_dir = os.path.dirname(settings.sqlite_db_path) or "."
        os.makedirs(db_dir, exist_ok=True)
        os.makedirs(settings.knowledge_base_path, exist_ok=True)

        event_store = SQLiteEventStore(settings.sqlite_db_path)
        await event_store.initialise()

        assessment_store = SQLiteAssessmentStore(settings.sqlite_db_path)
        await assessment_store.initialise()

        # ── Message bus ───────────────────────────────────────────────────────
        # Select adapter based on message_bus_type (falls back to message_bus_backend
        # for backward compatibility, then defaults to in_memory).
        bus_type = settings.message_bus_type or settings.message_bus_backend or "in_memory"
        message_bus: MessageBusPort
        if bus_type == "pubsub_emulator":
            message_bus = PubSubEmulatorMessageBus(
                project_id=settings.pubsub_project_id,
                emulator_host=settings.pubsub_emulator_host or "localhost:8085",
                settings=settings,
            )
            logger.info(
                "Message bus: Pub/Sub emulator",
                extra={
                    "project_id": settings.pubsub_project_id,
                    "emulator_host": settings.pubsub_emulator_host,
                },
            )
        else:
            message_bus = InMemoryMessageBus()
            logger.info("Message bus: in-memory")
        await message_bus.start()

        # ── Knowledge repository ──────────────────────────────────────────────
        knowledge_repo = LexicalKnowledgeRepository()
        doc_count = await knowledge_repo.load_from_directory(settings.knowledge_base_path)
        logger.info("Knowledge base ready", extra={"documents": doc_count})

        # ── Model provider ────────────────────────────────────────────────────
        model_provider: ModelProviderPort
        if settings.model_provider == "gemini" and settings.gemini_api_key:
            model_provider = GeminiModelProvider(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
            )
            logger.info("Model provider: Gemini", extra={"model": settings.gemini_model})
        else:
            model_provider = DeterministicModelProvider()
            logger.info("Model provider: deterministic (no API key required)")

        # ── Static data ───────────────────────────────────────────────────────
        clients, projects = await load_synthetic_data(settings.knowledge_base_path)

        # ── Services ──────────────────────────────────────────────────────────
        retrieval_service = RetrievalService(knowledge_repo)
        risk_scorer = RiskScorer()

        assessment_service = AssessmentService(
            assessment_store=assessment_store,
            retrieval_service=retrieval_service,
            model_provider=model_provider,
            risk_scorer=risk_scorer,
            clients=clients,
            projects=projects,
        )

        ingestion_service = IngestionService(event_store, message_bus)

        # ── Worker ────────────────────────────────────────────────────────────
        worker = EventProcessingWorker(
            message_bus=message_bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        return cls(
            event_store=event_store,
            assessment_store=assessment_store,
            message_bus=message_bus,
            knowledge_repo=knowledge_repo,
            model_provider=model_provider,
            ingestion_service=ingestion_service,
            retrieval_service=retrieval_service,
            risk_scorer=risk_scorer,
            assessment_service=assessment_service,
            worker=worker,
        )
