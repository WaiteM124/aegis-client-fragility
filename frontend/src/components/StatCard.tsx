import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: number | string;
  iconColour?: string;
  trend?: { value: number; label: string };
}

export function StatCard({ icon: Icon, label, value, iconColour = 'text-cyan-400', trend }: StatCardProps) {
  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 flex items-start gap-4">
      <div className={`p-2.5 rounded-lg bg-slate-700/50 ${iconColour}`}>
        <Icon size={22} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-400">{label}</p>
        <p className="text-2xl font-bold text-white mt-0.5">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </p>
        {trend && (
          <p className={`text-xs mt-1 ${trend.value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {trend.value >= 0 ? '+' : ''}{trend.value} {trend.label}
          </p>
        )}
      </div>
    </div>
  );
}
