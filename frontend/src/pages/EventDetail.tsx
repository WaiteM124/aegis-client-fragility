import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, ChevronDown, Activity } from 'lucide-react';
import { useEvent } from '../hooks/useEvent';
import { Badge } from '../components/Badge';
import { Skeleton } from '../components/Skeleton';
import { RiskGauge } from '../components/RiskGauge';
import { TraceModal } from '../components/TraceModal';
import { formatDate } from '../utils/dates';
import { riskColour } from '../utils/colours';
import type { RiskLevel } from '../types';

export default function EventDetail() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useEvent(id!);
  const [showTrace, setShowTrace] = useState(false);

  if (isLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-48" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-400 p-4 bg-red-900/20 rounded-xl border border-red-800">
        Failed to load event: {(error as Error).message}
      </div>
    );
  }

  if (!data) return null;

  const { event, classification, assessments } = data;
  const isProcessing = !['assessed', 'failed'].includes(event.status);

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Back */}
      <Link
        to="/events"
        className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
      >
        <ArrowLeft size={14} /> Back to Events
      </Link>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white leading-tight">{event.title}</h1>
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <Badge value={event.status} type="status" />
          {classification && (
            <>
              <Badge value={classification.severity} type="severity" />
              <Badge value={classification.category} type="status" />
            </>
          )}
          {isProcessing && (
            <span className="inline-flex items-center gap-1.5 text-xs text-blue-300 bg-blue-900/30 border border-blue-800/50 rounded-full px-2.5 py-0.5 animate-pulse">
              <Activity size={10} /> Processing…
            </span>
          )}
        </div>
      </div>

      {/* Metadata */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">Event Details</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <div>
            <span className="text-slate-500">Source:</span>{' '}
            <span className="text-slate-200">{event.source}</span>
          </div>
          {event.source_url && (
            <div>
              <span className="text-slate-500">Source URL:</span>{' '}
              <a
                href={event.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-400 hover:text-cyan-300 inline-flex items-center gap-1 transition-colors"
              >
                {event.source_url.length > 50 ? event.source_url.slice(0, 50) + '…' : event.source_url}
                <ExternalLink size={11} />
              </a>
            </div>
          )}
          {event.location && (
            <div>
              <span className="text-slate-500">Location:</span>{' '}
              <span className="text-slate-200">{event.location}</span>
            </div>
          )}
          <div>
            <span className="text-slate-500">Event Date:</span>{' '}
            <span className="text-slate-200">{formatDate(event.event_date)}</span>
          </div>
          <div>
            <span className="text-slate-500">Ingested At:</span>{' '}
            <span className="text-slate-200">{formatDate(event.ingested_at)}</span>
          </div>
          <div className="sm:col-span-2">
            <span className="text-slate-500">Correlation ID:</span>{' '}
            <span className="font-mono text-xs text-slate-300 break-all">{event.correlation_id}</span>
          </div>
        </div>

        {/* Regions */}
        {event.affected_regions?.length > 0 && (
          <div className="mt-4">
            <span className="text-slate-500 text-sm">Affected Regions:</span>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {event.affected_regions.map((r) => (
                <span key={r} className="text-xs bg-cyan-900/30 text-cyan-300 border border-cyan-800/40 rounded-full px-2.5 py-0.5">
                  {r}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Raw content */}
        <details className="mt-4">
          <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-200 flex items-center gap-1.5 transition-colors select-none">
            <ChevronDown size={14} />
            Raw Content
          </summary>
          <pre className="mt-3 bg-slate-900/60 border border-slate-700 rounded-lg p-4 text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
            {event.raw_content}
          </pre>
        </details>
      </div>

      {/* Classification */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">Classification</h2>
        {classification ? (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-slate-500">Category:</span>{' '}
                <span className="text-slate-200">{classification.category.replace(/_/g, ' ')}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-slate-500">Severity:</span>
                <Badge value={classification.severity} type="severity" />
              </div>
              <div>
                <span className="text-slate-500">Classifier Version:</span>{' '}
                <span className="font-mono text-xs text-slate-300">{classification.classifier_version}</span>
              </div>
              <div>
                <span className="text-slate-500">Classified At:</span>{' '}
                <span className="text-slate-200">{formatDate(classification.classified_at)}</span>
              </div>
            </div>
            {/* Confidence bar */}
            <div>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-slate-500">Confidence</span>
                <span className="text-slate-200 font-medium">{Math.round(classification.confidence * 100)}%</span>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-cyan-500 rounded-full transition-all"
                  style={{ width: `${classification.confidence * 100}%` }}
                />
              </div>
            </div>
            {classification.rationale && (
              <p className="text-slate-400 text-sm leading-relaxed">{classification.rationale}</p>
            )}
          </div>
        ) : (
          <p className="text-slate-500 text-sm">Classification not yet available.</p>
        )}
      </div>

      {/* Assessments */}
      {assessments && assessments.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            Assessments ({assessments.length})
          </h2>
          {assessments.map((assessment) => {
            // risk_level may be nested — check for it being present directly
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const anyAssessment = assessment as unknown as Record<string, unknown>;
            const riskScore = anyAssessment['risk_score'] as {
              overall_score: number;
              severity_component: number;
              exposure_component: number;
              confidence_component: number;
              risk_level: RiskLevel;
            } | undefined;

            const riskLevel = riskScore?.risk_level ?? 'minimal';
            const overallScore = riskScore?.overall_score ?? 0;
            const colour = riskColour[riskLevel] ?? '#64748b';

            return (
              <div
                key={assessment.id}
                className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4"
              >
                {/* Header */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm text-cyan-300">{assessment.client_id}</span>
                    <Badge value={riskLevel} type="risk" />
                  </div>
                  {riskScore && (
                    <RiskGauge score={overallScore} riskLevel={riskLevel} />
                  )}
                </div>

                {/* Score components */}
                {riskScore && (
                  <div className="space-y-2">
                    {[
                      { label: 'Severity', value: riskScore.severity_component },
                      { label: 'Exposure', value: riskScore.exposure_component },
                      { label: 'Confidence', value: riskScore.confidence_component },
                    ].map(({ label, value }) => (
                      <div key={label}>
                        <div className="flex justify-between text-xs text-slate-400 mb-1">
                          <span>{label}</span>
                          <span style={{ color: colour }}>{value?.toFixed(1) ?? '—'}</span>
                        </div>
                        <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${Math.min(value ?? 0, 100)}%`, backgroundColor: colour }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Assessment text */}
                <p className="text-slate-300 text-sm leading-relaxed">{assessment.assessment_text}</p>

                {/* Key risks */}
                {assessment.key_risks?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Key Risks</p>
                    <ul className="list-disc list-inside space-y-1">
                      {assessment.key_risks.map((risk, i) => (
                        <li key={i} className="text-slate-300 text-sm">{risk}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Recommended actions */}
                {assessment.recommended_actions?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Recommended Actions</p>
                    <ol className="list-decimal list-inside space-y-1">
                      {assessment.recommended_actions.map((action, i) => (
                        <li key={i} className="text-slate-300 text-sm">{action}</li>
                      ))}
                    </ol>
                  </div>
                )}

                {/* Model info */}
                <div className="pt-2 border-t border-slate-700 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span>{assessment.model_provider} · {assessment.model_version}</span>
                  {assessment.processing_duration_ms != null && (
                    <span>Processed in {assessment.processing_duration_ms.toLocaleString()}ms</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Full Trace button */}
      <div>
        <button
          onClick={() => setShowTrace(true)}
          className="px-4 py-2 bg-slate-700/50 hover:bg-slate-700 border border-slate-600 rounded-lg text-sm text-slate-200 transition-colors"
        >
          View Full Trace
        </button>
      </div>

      {showTrace && (
        <TraceModal eventId={id!} onClose={() => setShowTrace(false)} />
      )}
    </div>
  );
}
