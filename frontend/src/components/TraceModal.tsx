import { X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getTrace } from '../api/dashboard';
import { Badge } from './Badge';
import { Skeleton } from './Skeleton';
import { formatDate } from '../utils/dates';
import { riskColour } from '../utils/colours';
import type { RiskLevel } from '../types';

interface TraceModalProps {
  eventId: string;
  onClose: () => void;
}

export function TraceModal({ eventId, onClose }: TraceModalProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['trace', eventId],
    queryFn: () => getTrace(eventId),
  });

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative max-w-4xl w-full bg-slate-800 border border-slate-600 rounded-2xl p-6 overflow-y-auto max-h-[90vh]">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors"
          aria-label="Close"
        >
          <X size={20} />
        </button>

        <h2 className="text-xl font-bold text-white mb-1">Full Event Trace</h2>

        {isLoading && (
          <div className="space-y-3 mt-4">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}

        {error && (
          <p className="text-red-400 mt-4">Failed to load trace: {(error as Error).message}</p>
        )}

        {data && (
          <div className="space-y-6 mt-4">
            {/* Event header */}
            <div>
              <h3 className="text-lg font-semibold text-white">{data.event.title}</h3>
              <div className="flex items-center gap-2 mt-2">
                <Badge value={data.event.status} type="status" />
                {data.classification && (
                  <>
                    <Badge value={data.classification.severity} type="severity" />
                    <Badge value={data.classification.category} type="status" />
                  </>
                )}
              </div>
            </div>

            {/* Classification summary */}
            {data.classification && (
              <div className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                <h4 className="text-sm font-semibold text-slate-300 mb-2 uppercase tracking-wide">Classification</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-slate-500">Category:</span>{' '}
                    <span className="text-slate-200">{data.classification.category.replace(/_/g, ' ')}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Confidence:</span>{' '}
                    <span className="text-slate-200">{Math.round(data.classification.confidence * 100)}%</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Classifier:</span>{' '}
                    <span className="text-slate-200 font-mono text-xs">{data.classification.classifier_version}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Classified:</span>{' '}
                    <span className="text-slate-200">{formatDate(data.classification.classified_at)}</span>
                  </div>
                </div>
                {data.classification.rationale && (
                  <p className="text-slate-400 text-sm mt-3">{data.classification.rationale}</p>
                )}
              </div>
            )}

            {/* Assessments */}
            {data.assessments.length > 0 ? (
              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
                  Assessments ({data.assessments.length})
                </h4>
                {data.assessments.map((ta, idx) => {
                  const riskLevel = ta.risk_score?.risk_level as RiskLevel;
                  const colour = riskColour[riskLevel] ?? '#64748b';
                  return (
                    <div key={idx} className="bg-slate-700/30 border border-slate-600 rounded-xl p-4 space-y-3">
                      {/* Header */}
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-sm text-cyan-300">{ta.assessment.client_id}</span>
                        <div className="flex items-center gap-2">
                          <Badge value={riskLevel} type="risk" />
                          <span className="text-slate-400 text-sm">
                            Score:{' '}
                            <span style={{ color: colour }} className="font-bold">
                              {ta.risk_score?.overall_score?.toFixed(1) ?? '—'}
                            </span>
                          </span>
                        </div>
                      </div>

                      {/* Exposure */}
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div>
                          <span className="text-slate-500">Exposure Score:</span>{' '}
                          <span className="text-slate-200">{ta.risk_score?.exposure_component?.toFixed(1) ?? '—'}</span>
                        </div>
                        {ta.client_exposure?.matched_keywords?.length > 0 && (
                          <div>
                            <span className="text-slate-500">Keywords:</span>{' '}
                            <span className="text-slate-200">{ta.client_exposure.matched_keywords.join(', ')}</span>
                          </div>
                        )}
                        {ta.client_exposure?.matched_geography?.length > 0 && (
                          <div>
                            <span className="text-slate-500">Geography:</span>{' '}
                            <span className="text-slate-200">{ta.client_exposure.matched_geography.join(', ')}</span>
                          </div>
                        )}
                      </div>

                      {/* Assessment text */}
                      <p className="text-slate-300 text-sm leading-relaxed">{ta.assessment.assessment_text}</p>

                      {/* Key risks */}
                      {ta.assessment.key_risks?.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Key Risks</p>
                          <ul className="list-disc list-inside space-y-0.5">
                            {ta.assessment.key_risks.map((r, i) => (
                              <li key={i} className="text-slate-300 text-sm">{r}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Recommended actions */}
                      {ta.assessment.recommended_actions?.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Recommended Actions</p>
                          <ol className="list-decimal list-inside space-y-0.5">
                            {ta.assessment.recommended_actions.map((a, i) => (
                              <li key={i} className="text-slate-300 text-sm">{a}</li>
                            ))}
                          </ol>
                        </div>
                      )}

                      {/* Evidence references */}
                      {ta.assessment.evidence_references && ta.assessment.evidence_references.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Evidence References</p>
                          <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-slate-500 border-b border-slate-600">
                                  <th className="text-left py-1 pr-3">Document ID</th>
                                  <th className="text-left py-1 pr-3">Type</th>
                                  <th className="text-left py-1 pr-3">Relevance</th>
                                  <th className="text-left py-1">Excerpt</th>
                                </tr>
                              </thead>
                              <tbody>
                                {ta.assessment.evidence_references.map((ref, ri) => (
                                  <tr key={ri} className="border-b border-slate-700/50">
                                    <td className="py-1 pr-3 font-mono text-cyan-300 truncate max-w-[100px]">{ref.source_document_id}</td>
                                    <td className="py-1 pr-3 text-slate-400">{ref.source_type}</td>
                                    <td className="py-1 pr-3 text-slate-300">{(ref.relevance_score * 100).toFixed(0)}%</td>
                                    <td className="py-1 text-slate-400 truncate max-w-[200px]">{ref.content_excerpt}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-slate-500 text-sm">No assessments in trace.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
