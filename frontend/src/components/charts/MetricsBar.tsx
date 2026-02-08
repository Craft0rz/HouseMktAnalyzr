'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { PropertyWithMetrics } from '@/lib/types';
import { useTranslation } from '@/i18n/LanguageContext';

interface MetricsBarProps {
  properties: PropertyWithMetrics[];
  metric: 'score' | 'cap_rate' | 'cash_flow' | 'yield';
  className?: string;
}

const SCORE_LABEL_MAP: Record<string, string> = {
  cap_rate: 'score.capRate',
  cash_flow: 'score.cashFlow',
  price_per_unit: 'score.pricePerUnit',
  neighbourhood_safety: 'score.safety',
  neighbourhood_vacancy: 'score.lowVacancy',
  neighbourhood_rent_growth: 'score.rentGrowth',
  neighbourhood_affordability: 'score.affordability',
  condition: 'score.condition',
};

export function MetricsBar({ properties, metric, className }: MetricsBarProps) {
  const { t, locale } = useTranslation();

  const METRIC_CONFIG = {
    score: {
      label: t('chart.investmentScore'),
      getValue: (p: PropertyWithMetrics) => p.metrics.score,
      format: (v: number) => `${v}`,
      color: (v: number) => (v >= 70 ? '#22c55e' : v >= 50 ? '#eab308' : '#ef4444'),
    },
    cap_rate: {
      label: t('chart.capRate'),
      getValue: (p: PropertyWithMetrics) => p.metrics.cap_rate,
      format: (v: number) => `${v?.toFixed(1)}%`,
      color: (v: number) => (v >= 5 ? '#22c55e' : v >= 3 ? '#eab308' : '#ef4444'),
    },
    cash_flow: {
      label: t('chart.cashFlow'),
      getValue: (p: PropertyWithMetrics) => p.metrics.cash_flow_monthly,
      format: (v: number) => {
        const formatted = new Intl.NumberFormat(locale === 'fr' ? 'fr-CA' : 'en-CA', {
          style: 'currency', currency: 'CAD', maximumFractionDigits: 0,
        }).format(Math.abs(v));
        return v >= 0 ? formatted : `-${formatted}`;
      },
      color: (v: number) => (v >= 0 ? '#22c55e' : '#ef4444'),
    },
    yield: {
      label: t('chart.grossYield'),
      getValue: (p: PropertyWithMetrics) => p.metrics.gross_rental_yield,
      format: (v: number) => `${v?.toFixed(1)}%`,
      color: (v: number) => (v >= 6 ? '#22c55e' : v >= 4 ? '#eab308' : '#ef4444'),
    },
  };

  const config = METRIC_CONFIG[metric];

  const data = properties
    .map((p) => ({
      name: p.listing.address.split(',')[0].substring(0, 20),
      value: config.getValue(p) ?? 0,
      fullAddress: p.listing.address,
      scoreBreakdown: metric === 'score' ? p.metrics.score_breakdown : undefined,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  // Custom tooltip for score breakdown
  const ScoreTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: typeof data[number] }> }) => {
    if (!active || !payload?.length) return null;
    const entry = payload[0].payload;

    return (
      <div style={{
        backgroundColor: 'var(--popover)',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        color: 'var(--popover-foreground)',
        padding: '8px 12px',
        fontSize: '12px',
      }}>
        <p style={{ fontWeight: 600, marginBottom: 6 }}>{entry.fullAddress}</p>
        {metric === 'score' && entry.scoreBreakdown ? (
          <>
            {Object.entries(entry.scoreBreakdown)
              .sort(([, a], [, b]) => b - a)
              .map(([key, value]) => (
                <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, opacity: value > 0 ? 1 : 0.4 }}>
                  <span>{t(SCORE_LABEL_MAP[key] || key)}</span>
                  <span style={{ fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>{value.toFixed(1)}</span>
                </div>
              ))}
            <div style={{ borderTop: '1px solid var(--border)', marginTop: 4, paddingTop: 4, display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
              <span>{t('chart.total')}</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>{entry.value}</span>
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
            <span>{config.label}</span>
            <span style={{ fontWeight: 600 }}>{config.format(entry.value)}</span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 100, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            type="number"
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
            width={95}
          />
          <Tooltip
            content={<ScoreTooltip />}
            cursor={{ fill: 'var(--muted)', opacity: 0.3 }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={config.color(entry.value)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
