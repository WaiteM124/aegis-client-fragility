export const statusColour: Record<string, string> = {
  pending: 'bg-slate-700 text-slate-300',
  normalised: 'bg-blue-900/50 text-blue-300',
  classified: 'bg-blue-900/50 text-blue-300',
  published: 'bg-blue-900/50 text-blue-300',
  processing: 'bg-blue-900/50 text-blue-300',
  assessed: 'bg-green-900/50 text-green-300',
  failed: 'bg-red-900/50 text-red-300',
};

export const severityColour: Record<string, string> = {
  low: 'bg-blue-900/50 text-blue-300',
  medium: 'bg-amber-900/50 text-amber-300',
  high: 'bg-orange-900/50 text-orange-300',
  critical: 'bg-red-900/50 text-red-300',
};

export const riskColour: Record<string, string> = {
  minimal: '#64748b',
  low: '#3b82f6',
  moderate: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
};

export const riskBadgeColour: Record<string, string> = {
  minimal: 'bg-slate-700 text-slate-300',
  low: 'bg-blue-900/50 text-blue-300',
  moderate: 'bg-amber-900/50 text-amber-300',
  high: 'bg-orange-900/50 text-orange-300',
  critical: 'bg-red-900/50 text-red-300',
};
