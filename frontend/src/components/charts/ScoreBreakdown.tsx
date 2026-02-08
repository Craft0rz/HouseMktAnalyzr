'use client';

interface ScoreBreakdownProps {
  scoreBreakdown: Record<string, number>;
  className?: string;
}

const FINANCIAL_CATEGORIES: { key: string; label: string; max: number }[] = [
  { key: 'cap_rate', label: 'Cap Rate', max: 25 },
  { key: 'cash_flow', label: 'Cash Flow', max: 25 },
  { key: 'price_per_unit', label: 'Price/Unit', max: 20 },
];

const LOCATION_CATEGORIES: { key: string; label: string; max: number }[] = [
  { key: 'neighbourhood_safety', label: 'Safety', max: 8 },
  { key: 'neighbourhood_vacancy', label: 'Low Vacancy', max: 7 },
  { key: 'neighbourhood_rent_growth', label: 'Rent Growth', max: 7 },
  { key: 'neighbourhood_affordability', label: 'Affordability', max: 4 },
  { key: 'condition', label: 'Condition', max: 4 },
];

function getBarColor(percentage: number): string {
  if (percentage >= 75) return 'bg-green-500';
  if (percentage >= 50) return 'bg-yellow-500';
  if (percentage >= 25) return 'bg-orange-500';
  return 'bg-red-500';
}

export function ScoreBreakdown({ scoreBreakdown, className }: ScoreBreakdownProps) {
  if (!scoreBreakdown || Object.keys(scoreBreakdown).length === 0) return null;

  const hasLocation = LOCATION_CATEGORIES.some(
    ({ key }) => scoreBreakdown[key] != null
  );

  const financialTotal = FINANCIAL_CATEGORIES.reduce(
    (sum, { key }) => sum + (scoreBreakdown[key] ?? 0), 0
  );
  const locationTotal = hasLocation
    ? LOCATION_CATEGORIES.reduce(
        (sum, { key }) => sum + (scoreBreakdown[key] ?? 0), 0
      )
    : 0;

  return (
    <div className={`space-y-3 ${className || ''}`}>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-medium">Financial</span>
        <span className="tabular-nums">{financialTotal.toFixed(0)}/70</span>
      </div>
      {FINANCIAL_CATEGORIES.map(({ key, label, max }) => {
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

      {hasLocation && (
        <>
          <div className="pt-1 border-t flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium">Location & Quality</span>
            <span className="tabular-nums">{locationTotal.toFixed(0)}/30</span>
          </div>
          {LOCATION_CATEGORIES.filter(({ key }) => scoreBreakdown[key] != null).map(({ key, label, max }) => {
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
                    className={`h-full rounded-full transition-all bg-blue-500`}
                    style={{ width: `${Math.min(100, percentage)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
