import { useState } from 'react';
import { ShieldCheck, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAssessments } from '../hooks/useAssessments';
import { Badge } from '../components/Badge';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { formatDate } from '../utils/dates';
import type { RiskLevel } from '../types';

const PAGE_SIZE = 20;

export default function Assessments() {
  const [offset, setOffset] = useState(0);
  const [clientIdFilter, setClientIdFilter] = useState('');
  const [appliedClientId, setAppliedClientId] = useState('');

  const { data, isLoading, error } = useAssessments(PAGE_SIZE, offset, appliedClientId || undefined);

  const totalCount = data?.count ?? 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  function handleSearch() {
    setAppliedClientId(clientIdFilter.trim());
    setOffset(0);
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-white">Assessments</h1>
        <p className="text-slate-400 text-sm mt-1">{totalCount.toLocaleString()} total assessments</p>
      </div>

      {/* Client ID filter */}
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Filter by Client ID…"
          value={clientIdFilter}
          onChange={(e) => setClientIdFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-cyan-500 transition-colors min-w-[220px]"
        />
        <button
          onClick={handleSearch}
          className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-sm rounded-lg transition-colors"
        >
          Search
        </button>
        {appliedClientId && (
          <button
            onClick={() => { setClientIdFilter(''); setAppliedClientId(''); setOffset(0); }}
            className="px-3 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wide border-b border-slate-700 bg-slate-800/80">
                <th className="text-left px-4 py-3">Client ID</th>
                <th className="text-left px-4 py-3">Event ID</th>
                <th className="text-left px-4 py-3">Risk Level</th>
                <th className="text-left px-4 py-3">Score</th>
                <th className="text-left px-4 py-3">First Key Risk</th>
                <th className="text-left px-4 py-3">Assessed At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={6} className="px-4 py-3">
                      <Skeleton className="h-6" />
                    </td>
                  </tr>
                ))
              ) : data?.assessments && data.assessments.length > 0 ? (
                data.assessments.map((item, idx) => {
                  const a = item.assessment;
                  const rs = item.risk_score;
                  const riskLevel = (rs?.risk_level ?? '') as RiskLevel;

                  return (
                    <tr key={a.id ?? idx} className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-4 py-3 font-mono text-sm text-cyan-300">{a.client_id}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-400 max-w-[160px] truncate">{a.event_id}</td>
                      <td className="px-4 py-3">
                        {riskLevel ? (
                          <Badge value={riskLevel} type="risk" />
                        ) : (
                          <span className="text-slate-500 text-sm">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-300">
                        {rs?.overall_score != null ? rs.overall_score.toFixed(1) : '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-sm max-w-[280px] truncate">
                        {a.key_risks?.[0] ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-sm whitespace-nowrap">
                        {formatDate(a.assessed_at)}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6}>
                    <EmptyState
                      icon={ShieldCheck}
                      title="No assessments found"
                      description={appliedClientId ? `No assessments for client "${appliedClientId}".` : undefined}
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {!isLoading && totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
            <span className="text-xs text-slate-500">
              Page {currentPage} of {totalPages} ({totalCount.toLocaleString()} assessments)
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-slate-700/50 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft size={14} /> Prev
              </button>
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= totalCount}
                className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-slate-700/50 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="text-red-400 p-4 bg-red-900/20 rounded-xl border border-red-800">
          Failed to load assessments: {(error as Error).message}
        </div>
      )}
    </div>
  );
}
