import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Globe, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import { useEvents } from '../hooks/useEvents';
import { Badge } from '../components/Badge';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { formatRelative } from '../utils/dates';
import type { EventStatus } from '../types';

const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'all', label: 'All Statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'normalised', label: 'Normalised' },
  { value: 'classified', label: 'Classified' },
  { value: 'published', label: 'Published' },
  { value: 'processing', label: 'Processing' },
  { value: 'assessed', label: 'Assessed' },
  { value: 'failed', label: 'Failed' },
];

const PAGE_SIZE = 20;

export default function Events() {
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [titleSearch, setTitleSearch] = useState('');

  const { data, isLoading, error } = useEvents(PAGE_SIZE, offset);

  const filteredEvents = (data?.events ?? []).filter((event) => {
    const matchesStatus = statusFilter === 'all' || event.status === (statusFilter as EventStatus);
    const matchesTitle = titleSearch === '' || event.title.toLowerCase().includes(titleSearch.toLowerCase());
    return matchesStatus && matchesTitle;
  });

  const totalCount = data?.count ?? 0;
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-white">Events</h1>
        <p className="text-slate-400 text-sm mt-1">
          {totalCount.toLocaleString()} total events
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setOffset(0); }}
          className="bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500 transition-colors"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-slate-800">
              {opt.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Search by title…"
          value={titleSearch}
          onChange={(e) => setTitleSearch(e.target.value)}
          className="bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-cyan-500 transition-colors min-w-[220px]"
        />
      </div>

      {/* Table */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wide border-b border-slate-700 bg-slate-800/80">
                <th className="text-left px-4 py-3">Title</th>
                <th className="text-left px-4 py-3">Source</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Severity</th>
                <th className="text-left px-4 py-3">Category</th>
                <th className="text-left px-4 py-3">Regions</th>
                <th className="text-left px-4 py-3">Time</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={8} className="px-4 py-3">
                      <Skeleton className="h-6" />
                    </td>
                  </tr>
                ))
              ) : filteredEvents.length > 0 ? (
                filteredEvents.map((event) => (
                  <tr key={event.id} className="hover:bg-slate-700/20 transition-colors">
                    <td className="px-4 py-3 max-w-[280px]">
                      <Link
                        to={`/events/${event.id}`}
                        className="text-slate-200 hover:text-cyan-400 transition-colors text-sm"
                      >
                        {event.title.length > 80 ? event.title.slice(0, 80) + '…' : event.title}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-sm max-w-[120px] truncate">
                      {event.source}
                    </td>
                    <td className="px-4 py-3">
                      <Badge value={event.status} type="status" />
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-slate-500 text-sm">—</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-slate-500 text-sm">—</span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-sm max-w-[160px] truncate">
                      {event.affected_regions?.join(', ') || '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-sm whitespace-nowrap">
                      {formatRelative(event.ingested_at)}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/events/${event.id}`}
                        className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                      >
                        <ExternalLink size={12} />
                        View
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>
                    <EmptyState
                      icon={Globe}
                      title="No events found"
                      description={titleSearch || statusFilter !== 'all' ? 'Try adjusting your filters.' : undefined}
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
              Page {currentPage} of {totalPages} ({totalCount.toLocaleString()} events)
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
          Failed to load events: {(error as Error).message}
        </div>
      )}
    </div>
  );
}
