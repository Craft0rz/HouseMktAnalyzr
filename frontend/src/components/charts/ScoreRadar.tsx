'use client';

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';

interface ScoreRadarProps {
  scoreBreakdown: Record<string, number>;
  className?: string;
}

const SCORE_LABELS: Record<string, string> = {
  yield_score: 'Yield',
  cap_rate_score: 'Cap Rate',
  cash_flow_score: 'Cash Flow',
  price_score: 'Price/Unit',
  assessment_score: 'Assessment',
};

// Max score per category (5 categories, max 20 each = 100 total)
const MAX_SCORE_PER_CATEGORY = 20;

export function ScoreRadar({ scoreBreakdown, className }: ScoreRadarProps) {
  const data = Object.entries(scoreBreakdown).map(([key, value]) => ({
    metric: SCORE_LABELS[key] || key.replace('_score', '').replace('_', ' '),
    value: Math.round(value),
    fullMark: MAX_SCORE_PER_CATEGORY,
    // Target line at 15 (75% of max)
    target: 15,
  }));

  if (data.length === 0) return null;

  // Calculate average score percentage for color
  const avgPercentage = data.reduce((acc, d) => acc + d.value, 0) / (data.length * MAX_SCORE_PER_CATEGORY) * 100;
  const fillColor = avgPercentage >= 70 ? '#22c55e' : avgPercentage >= 50 ? '#eab308' : '#ef4444';

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} margin={{ top: 10, right: 40, bottom: 10, left: 40 }}>
          <PolarGrid
            stroke="hsl(var(--border))"
            strokeDasharray="3 3"
          />
          <PolarAngleAxis
            dataKey="metric"
            tick={{
              fill: 'hsl(var(--foreground))',
              fontSize: 11,
              fontWeight: 500,
            }}
            tickLine={false}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, MAX_SCORE_PER_CATEGORY]}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 9 }}
            tickCount={5}
            axisLine={false}
          />
          {/* Target reference area */}
          <Radar
            name="Target (15)"
            dataKey="target"
            stroke="hsl(var(--muted-foreground))"
            fill="none"
            strokeWidth={1}
            strokeDasharray="4 4"
            strokeOpacity={0.5}
          />
          {/* Actual score */}
          <Radar
            name="Your Score"
            dataKey="value"
            stroke={fillColor}
            fill={fillColor}
            fillOpacity={0.25}
            strokeWidth={2}
            dot={{ r: 4, fill: fillColor, strokeWidth: 0 }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--popover))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '8px',
              padding: '8px 12px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
            }}
            labelStyle={{ color: 'hsl(var(--popover-foreground))', fontWeight: 600 }}
            formatter={(value: number) => [`${value}/20`, 'Score']}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
