'use client';

import { useTranslation } from '@/i18n/LanguageContext';

interface ScoreBreakdownProps {
  scoreBreakdown: Record<string, number>;
  className?: string;
}

const FINANCIAL_KEYS = [
  { key: 'cap_rate', labelKey: 'score.capRate', max: 25 },
  { key: 'cash_flow', labelKey: 'score.cashFlow', max: 25 },
  { key: 'price_per_unit', labelKey: 'score.pricePerUnit', max: 20 },
];

const LOCATION_KEYS = [
  { key: 'neighbourhood_safety', labelKey: 'score.safety', max: 8 },
  { key: 'neighbourhood_vacancy', labelKey: 'score.lowVacancy', max: 7 },
  { key: 'neighbourhood_rent_growth', labelKey: 'score.rentGrowth', max: 7 },
  { key: 'neighbourhood_affordability', labelKey: 'score.affordability', max: 4 },
  { key: 'condition', labelKey: 'score.condition', max: 4 },
];

function getBarColor(percentage: number): string {
  if (percentage >= 75) return 'bg-green-500';
  if (percentage >= 50) return 'bg-yellow-500';
  if (percentage >= 25) return 'bg-orange-500';
  return 'bg-red-500';
}

export function ScoreBreakdown({ scoreBreakdown, className }: ScoreBreakdownProps) {
  const { t } = useTranslation();

  if (!scoreBreakdown || Object.keys(scoreBreakdown).length === 0) return null;

  const hasLocation = LOCATION_KEYS.some(
    ({ key }) => scoreBreakdown[key] != null
  );

  const financialTotal = FINANCIAL_KEYS.reduce(
    (sum, { key }) => sum + (scoreBreakdown[key] ?? 0), 0
  );
  const locationTotal = hasLocation
    ? LOCATION_KEYS.reduce(
        (sum, { key }) => sum + (scoreBreakdown[key] ?? 0), 0
      )
    : 0;

  return (
    <div className={`space-y-3 ${className || ''}`}>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-medium">{t('score.financial')}</span>
        <span className="tabular-nums">{financialTotal.toFixed(0)}/70</span>
      </div>
      {FINANCIAL_KEYS.map(({ key, labelKey, max }) => {
        const value = scoreBreakdown[key] ?? 0;
        const percentage = (value / max) * 100;

        return (
          <div key={key} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{t(labelKey)}</span>
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
            <span className="font-medium">{t('score.locationQuality')}</span>
            <span className="tabular-nums">{locationTotal.toFixed(0)}/30</span>
          </div>
          {LOCATION_KEYS.filter(({ key }) => scoreBreakdown[key] != null).map(({ key, labelKey, max }) => {
            const value = scoreBreakdown[key] ?? 0;
            const percentage = (value / max) * 100;

            return (
              <div key={key} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{t(labelKey)}</span>
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
