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
  LabelList,
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

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat(locale === 'fr' ? 'fr-CA' : 'en-CA', {
      style: 'currency',
      currency: 'CAD',
      maximumFractionDigits: 0,
    }).format(v);

  const formatCashFlowValue = (v: number) => {
    const formatted = formatCurrency(Math.abs(v));
    return v >= 0 ? formatted : `-${formatted}`;
  };

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
      format: (v: number) => formatCashFlowValue(v),
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
      price: p.listing.price,
      units: p.listing.units,
      propertyType: p.listing.property_type,
      monthlyRent: p.metrics.estimated_monthly_rent,
      annualRent: p.metrics.annual_rent,
      capRate: p.metrics.cap_rate,
      cashFlow: p.metrics.cash_flow_monthly,
      grossYield: p.metrics.gross_rental_yield,
      pricePerUnit: p.metrics.price_per_unit,
      score: p.metrics.score,
      totalExpenses: p.listing.total_expenses,
      netIncome: p.listing.net_income,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  const tooltipStyle = {
    backgroundColor: 'var(--popover)',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    color: 'var(--popover-foreground)',
    padding: '8px 12px',
    fontSize: '12px',
  };

  const rowStyle = { display: 'flex' as const, justifyContent: 'space-between' as const, gap: 16 };
  const boldRowStyle = { ...rowStyle, fontWeight: 600 as const };
  const dividerStyle = { borderTop: '1px solid var(--border)', marginTop: 4, paddingTop: 4 };
  const tabNum = { fontVariantNumeric: 'tabular-nums' as const };

  const DetailTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: typeof data[number] }> }) => {
    if (!active || !payload?.length) return null;
    const entry = payload[0].payload;

    const propertyHeader = (
      <>
        <p style={{ fontWeight: 600, marginBottom: 2 }}>{entry.fullAddress}</p>
        <p style={{ opacity: 0.6, marginBottom: 6 }}>
          {t(`propertyTypes.${entry.propertyType}`)} · {entry.units} {t('common.units')}
        </p>
      </>
    );

    const scoreFooter = (
      <div style={{ ...rowStyle, ...dividerStyle }}>
        <span>{t('chart.score')}</span>
        <span style={{ fontWeight: 500, ...tabNum }}>{entry.score}/100</span>
      </div>
    );

    // Score breakdown
    if (metric === 'score' && entry.scoreBreakdown) {
      return (
        <div style={tooltipStyle}>
          <p style={{ fontWeight: 600, marginBottom: 6 }}>{entry.fullAddress}</p>
          {Object.entries(entry.scoreBreakdown)
            .sort(([, a], [, b]) => b - a)
            .map(([key, value]) => (
              <div key={key} style={{ ...rowStyle, opacity: value > 0 ? 1 : 0.4 }}>
                <span>{t(SCORE_LABEL_MAP[key] || key)}</span>
                <span style={{ fontWeight: 500, ...tabNum }}>{value.toFixed(1)}</span>
              </div>
            ))}
          <div style={{ ...boldRowStyle, ...dividerStyle }}>
            <span>{t('chart.total')}</span>
            <span style={tabNum}>{entry.value}</span>
          </div>
        </div>
      );
    }

    // Cap Rate detailed
    if (metric === 'cap_rate') {
      const noi =
        entry.netIncome != null
          ? entry.netIncome
          : entry.annualRent && entry.totalExpenses != null
            ? entry.annualRent - entry.totalExpenses
            : null;

      return (
        <div style={tooltipStyle}>
          {propertyHeader}
          <div style={boldRowStyle}>
            <span>{t('chart.capRate')}</span>
            <span style={tabNum}>{entry.capRate?.toFixed(2)}%</span>
          </div>
          <div style={dividerStyle} />
          <div style={rowStyle}>
            <span>{t('chart.price')}</span>
            <span style={tabNum}>{formatCurrency(entry.price)}</span>
          </div>
          <div style={rowStyle}>
            <span>{t('chart.annualRent')}</span>
            <span style={tabNum}>{formatCurrency(entry.annualRent)}</span>
          </div>
          {entry.totalExpenses != null && (
            <div style={rowStyle}>
              <span>{t('chart.expenses')}</span>
              <span style={tabNum}>{formatCurrency(entry.totalExpenses)}</span>
            </div>
          )}
          {noi != null && (
            <div style={rowStyle}>
              <span>{t('chart.noi')}</span>
              <span style={tabNum}>{formatCurrency(noi)}</span>
            </div>
          )}
        </div>
      );
    }

    // Cash Flow detailed
    if (metric === 'cash_flow') {
      return (
        <div style={tooltipStyle}>
          {propertyHeader}
          <div style={boldRowStyle}>
            <span>{t('chart.cashFlow')}</span>
            <span style={{ ...tabNum, color: (entry.cashFlow ?? 0) >= 0 ? '#22c55e' : '#ef4444' }}>
              {formatCashFlowValue(entry.cashFlow ?? 0)}{t('common.perMonth')}
            </span>
          </div>
          <div style={dividerStyle} />
          <div style={rowStyle}>
            <span>{t('chart.monthlyRent')}</span>
            <span style={tabNum}>{formatCurrency(entry.monthlyRent)}</span>
          </div>
          <div style={rowStyle}>
            <span>{t('chart.price')}</span>
            <span style={tabNum}>{formatCurrency(entry.price)}</span>
          </div>
          {entry.totalExpenses != null && (
            <div style={rowStyle}>
              <span>{t('chart.expenses')}</span>
              <span style={tabNum}>{formatCurrency(entry.totalExpenses)}{t('common.perMonth')}</span>
            </div>
          )}
        </div>
      );
    }

    // Yield detailed
    if (metric === 'yield') {
      return (
        <div style={tooltipStyle}>
          {propertyHeader}
          <div style={boldRowStyle}>
            <span>{t('chart.grossYield')}</span>
            <span style={tabNum}>{entry.grossYield?.toFixed(2)}%</span>
          </div>
          <div style={dividerStyle} />
          <div style={rowStyle}>
            <span>{t('chart.annualRent')}</span>
            <span style={tabNum}>{formatCurrency(entry.annualRent)}</span>
          </div>
          <div style={rowStyle}>
            <span>{t('chart.price')}</span>
            <span style={tabNum}>{formatCurrency(entry.price)}</span>
          </div>
        </div>
      );
    }

    // Fallback
    return (
      <div style={tooltipStyle}>
        <p style={{ fontWeight: 600, marginBottom: 6 }}>{entry.fullAddress}</p>
        <div style={rowStyle}>
          <span>{config.label}</span>
          <span style={{ fontWeight: 600 }}>{config.format(entry.value)}</span>
        </div>
      </div>
    );
  };

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 60, left: 100, bottom: 5 }}>
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
            content={<DetailTooltip />}
            cursor={{ fill: 'var(--muted)', opacity: 0.3 }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={config.color(entry.value)} />
            ))}
            <LabelList
              dataKey="value"
              position="right"
              formatter={(v) => config.format(Number(v))}
              style={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
