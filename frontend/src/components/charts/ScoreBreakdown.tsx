'use client';

interface ScoreBreakdownProps {
  scoreBreakdown: Record<string, number>;
  className?: string;
}

const CATEGORIES: { key: string; label: string; max: number }[] = [
  { key: 'cap_rate', label: 'Cap Rate', max: 25 },
  { key: 'cash_flow', label: 'Cash Flow', max: 25 },
  { key: 'price_per_unit', label: 'Price/Unit', max: 20 },
  { key: 'gross_yield', label: 'Gross Yield', max: 15 },
  { key: 'grm', label: 'GRM', max: 15 },
];

function getBarColor(percentage: number): string {
  if (percentage >= 75) return 'bg-green-500';
  if (percentage >= 50) return 'bg-yellow-500';
  if (percentage >= 25) return 'bg-orange-500';
  return 'bg-red-500';
}

export function ScoreBreakdown({ scoreBreakdown, className }: ScoreBreakdownProps) {
  if (!scoreBreakdown || Object.keys(scoreBreakdown).length === 0) return null;

  return (
    <div className={`space-y-3 ${className || ''}`}>
      {CATEGORIES.map(({ key, label, max }) => {
        const value = scoreBreakdown[key] ?? 0;
        const percentage = (value / max) * 100;

        return (
          <div key={key} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{label}</span>
              <span className="text-muted-foreground tabular-nums">
                {value.toFixed(0)}/{max}
              </span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${getBarColor(percentage)}`}
                style={{ width: `${Math.min(100, percentage)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
