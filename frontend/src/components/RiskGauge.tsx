import { riskColour } from '../utils/colours';
import type { RiskLevel } from '../types';

interface RiskGaugeProps {
  score: number;
  riskLevel: RiskLevel;
}

const r = 52;
const cx = 60;
const cy = 60;
const strokeWidth = 8;
const circumference = 2 * Math.PI * r; // ≈ 326.7

export function RiskGauge({ score, riskLevel }: RiskGaugeProps) {
  const filled = circumference * (Math.min(Math.max(score, 0), 100) / 100);
  const colour = riskColour[riskLevel] ?? '#64748b';

  return (
    <svg width={120} height={120} viewBox="0 0 120 120">
      {/* Background circle */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke="#1e293b"
        strokeWidth={strokeWidth}
      />
      {/* Filled arc */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={colour}
        strokeWidth={strokeWidth}
        strokeDasharray={`${filled} ${circumference - filled}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition: 'stroke-dasharray 0.5s ease' }}
      />
      {/* Score text */}
      <text
        x={cx}
        y={cy - 6}
        textAnchor="middle"
        dominantBaseline="middle"
        fill="white"
        fontSize="20"
        fontWeight="bold"
      >
        {Math.round(score)}
      </text>
      {/* Risk level label */}
      <text
        x={cx}
        y={cy + 14}
        textAnchor="middle"
        dominantBaseline="middle"
        fill={colour}
        fontSize="9"
        fontWeight="500"
      >
        {riskLevel.toUpperCase()}
      </text>
    </svg>
  );
}
