"""
Firestore persistence adapters.

Implements EventStorePort and AssessmentStorePort using Google Cloud Firestore.
Used when PERSISTENCE_BACKEND=firestore_emulator (or firestore in production).

Collection names:
  - aegis_events            (Event documents)
  - aegis_classifications   (EventClassification documents, keyed by event_id)
  - aegis_assessments       (ImpactAssessment documents)
  - aegis_risk_scores       (RiskScore documents, keyed by assessment_id)
  - aegis_exposures         (ClientExposure documents)

The Firestore Python client is synchronous; all calls are wrapped with
asyncio.to_thread to avoid blocking the event loop.
"""
