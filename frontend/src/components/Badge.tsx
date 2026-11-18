import { statusColour, severityColour, riskBadgeColour } from '../utils/colours';

interface BadgeProps {
  value: string;
  type: 'status' | 'severity' | 'risk';
}

export function Badge({ value, type }: BadgeProps) {
  let colourClass = 'bg-slate-700 text-slate-300';

  if (type === 'status') {
    colourClass = statusColour[value] ?? 'bg-slate-700 text-slate-300';
  } else if (type === 'severity') {
    colourClass = severityColour[value] ?? 'bg-slate-700 text-slate-300';
  } else if (type === 'risk') {
    colourClass = riskBadgeColour[value] ?? 'bg-slate-700 text-slate-300';
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colourClass}`}>
      {value.replace(/_/g, ' ')}
    </span>
  );
}
