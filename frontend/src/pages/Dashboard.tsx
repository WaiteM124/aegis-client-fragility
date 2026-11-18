import { Link } from 'react-router-dom';
import { Globe, ShieldCheck, Users, Briefcase } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts';
import { useSummary } from '../hooks/useSummary';
import { StatCard } from '../components/StatCard';
import { Badge } from '../components/Badge';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { formatDate } from '../utils/dates';
import { riskBadgeColour } from '../utils/colours';
import type { RiskLevel } from '../types';

const RISK_COLOURS: Record<string, string> = {
  minimal: '#64748b',
  low: '#3b82f6',
  moderate: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
};

function titleCase(str: string) {
  return str.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

const tooltipStyle = {
  backgroundColor: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 8,
  color: '#f1f5f9',
};

export default function Dashboard() {
  const { data, isLoading, error } = useSummary();

  if (error) {
    return (
      <div className="text-red-400 p-4 bg-red-900/20 rounded-xl border border-red-800">
        Failed to load dashboard: {(error as Error).message}
      </div>
    );
  }

  const categoryData = data
    ? Object.entries(data.category_breakdown).map(([name, value]) => ({
        name: titleCase(name),
        value,
      }))
    : [];

  const riskData = data
    ? Object.entries(data.risk_level_breakdown).map(([name, value]) => ({
        name: titleCase(name),
        value,
      }))
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">Real-time intelligence overview</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))
        ) : data ? (
          <>
            <StatCard icon={Globe} label="Total Events" value={data.total_events} iconColour="text-cyan-400" />
            <StatCard icon={ShieldCheck} label="Total Assessments" value={data.total_assessments} iconColour="text-purple-400" />
            <StatCard icon={Users} label="Clients Affected" value={data.affected_clients} iconColour="text-amber-400" />
            <StatCard icon={Briefcase} label="Projects Affected" value={data.affected_projects} iconColour="text-blue-400" />
          </>
        ) : null}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Category Bar Chart */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">Events by Category</h2>
          {isLoading ? (
            <Skeleton className="h-64" />
          ) : categoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={categoryData} margin={{ top: 0, right: 0, left: -20, bottom: 60 }}>
                <XAxis
                  dataKey="name"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  angle={-35}
                  textAnchor="end"
                  interval={0}
                  stroke="transparent"
                />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} stroke="transparent" />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
                <Bar dataKey="value" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState icon={Globe} title="No category data" />
          )}
        </div>

        {/* Risk Level Donut */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">Risk Level Distribution</h2>
          {isLoading ? (
            <Skeleton className="h-64" />
          ) : riskData.length > 0 ? (
            <div className="flex flex-col items-center">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={riskData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    dataKey="value"
                    paddingAngle={3}
                  >
                    {riskData.map((entry) => (
                      <Cell
                        key={entry.name}
                        fill={RISK_COLOURS[entry.name.toLowerCase()] ?? '#64748b'}
                      />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              {/* Custom legend */}
              <div className="flex flex-wrap justify-center gap-3 mt-2">
                {riskData.map((entry) => (
                  <div key={entry.name} className="flex items-center gap-1.5">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: RISK_COLOURS[entry.name.toLowerCase()] ?? '#64748b' }}
                    />
                    <span className="text-xs text-slate-400">
                      {entry.name} ({entry.value})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState icon={ShieldCheck} title="No risk data" />
          )}
        </div>
      </div>

      {/* Recent Events */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">Recent Events</h2>
          <Link to="/events" className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors">
            View all →
          </Link>
        </div>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10" />)}
          </div>
        ) : data?.recent_events && data.recent_events.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-slate-500 uppercase tracking-wide border-b border-slate-700">
                  <th className="text-left py-2 pr-4">Title</th>
                  <th className="text-left py-2 pr-4">Status</th>
                  <th className="text-left py-2 pr-4">Severity</th>
                  <th className="text-left py-2">Ingested</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {data.recent_events.map((event) => (
                  <tr key={event.id} className="hover:bg-slate-700/20 transition-colors">
                    <td className="py-2.5 pr-4">
                      <Link
                        to={`/events/${event.id}`}
                        className="text-slate-200 hover:text-cyan-400 transition-colors text-sm"
                      >
                        {event.title.length > 80 ? event.title.slice(0, 80) + '…' : event.title}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-4">
                      <Badge value={event.status} type="status" />
                    </td>
                    <td className="py-2.5 pr-4">
                      {/* Severity not on list response — show dash */}
                      <span className="text-slate-500 text-sm">—</span>
                    </td>
                    <td className="py-2.5 text-slate-400 text-sm">{formatDate(event.ingested_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon={Globe} title="No recent events" />
        )}
      </div>

      {/* Recent Assessments */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">Recent Assessments</h2>
          <Link to="/assessments" className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors">
            View all →
          </Link>
        </div>
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32" />)}
          </div>
        ) : data?.recent_assessments && data.recent_assessments.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {data.recent_assessments.map((assessment) => {
              // risk_level may come from assessment via risk_score — not directly on Assessment type
              // Use assessment as typed; risk_level would be on a risk_score subfield if present
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const riskLevel = (assessment as unknown as Record<string, unknown>)['risk_level'] as RiskLevel | undefined;
              const badgeColour = riskLevel ? (riskBadgeColour[riskLevel] ?? 'bg-slate-700 text-slate-300') : 'bg-slate-700 text-slate-300';

              return (
                <div
                  key={assessment.id}
                  className="bg-slate-700/30 border border-slate-600 rounded-xl p-4 space-y-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-sm font-semibold text-slate-200 truncate">{assessment.client_id}</span>
                    {riskLevel && (
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${badgeColour}`}>
                        {riskLevel}
                      </span>
                    )}
                  </div>
                  {assessment.key_risks?.slice(0, 2).map((risk, i) => (
                    <div key={i} className="flex items-start gap-1.5">
                      <span className="text-cyan-400 mt-1 shrink-0">•</span>
                      <span className="text-slate-400 text-xs leading-snug">{risk}</span>
                    </div>
                  ))}
                  <p className="text-slate-500 text-xs pt-1">{formatDate(assessment.assessed_at)}</p>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState icon={ShieldCheck} title="No recent assessments" />
        )}
      </div>
    </div>
  );
}

