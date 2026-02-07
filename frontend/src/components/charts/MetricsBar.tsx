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

interface MetricsBarProps {
  properties: PropertyWithMetrics[];
  metric: 'score' | 'cap_rate' | 'cash_flow' | 'yield';
  className?: string;
}

const METRIC_CONFIG = {
  score: {
    label: 'Investment Score',
    getValue: (p: PropertyWithMetrics) => p.metrics.score,
    format: (v: number) => `${v}`,
    color: (v: number) => (v >= 70 ? '#22c55e' : v >= 50 ? '#eab308' : '#ef4444'),
  },
  cap_rate: {
    label: 'Cap Rate (%)',
    getValue: (p: PropertyWithMetrics) => p.metrics.cap_rate,
    format: (v: number) => `${v?.toFixed(1)}%`,
    color: (v: number) => (v >= 5 ? '#22c55e' : v >= 3 ? '#eab308' : '#ef4444'),
  },
  cash_flow: {
    label: 'Monthly Cash Flow ($)',
    getValue: (p: PropertyWithMetrics) => p.metrics.cash_flow_monthly,
    format: (v: number) => `$${v?.toLocaleString()}`,
    color: (v: number) => (v >= 0 ? '#22c55e' : '#ef4444'),
  },
  yield: {
    label: 'Gross Yield (%)',
    getValue: (p: PropertyWithMetrics) => p.metrics.gross_rental_yield,
    format: (v: number) => `${v?.toFixed(1)}%`,
    color: (v: number) => (v >= 6 ? '#22c55e' : v >= 4 ? '#eab308' : '#ef4444'),
  },
};

export function MetricsBar({ properties, metric, className }: MetricsBarProps) {
  const config = METRIC_CONFIG[metric];

  const data = properties
    .map((p) => ({
      name: p.listing.address.split(',')[0].substring(0, 20),
      value: config.getValue(p) ?? 0,
      fullAddress: p.listing.address,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 100, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            type="number"
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
            width={95}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--popover))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
            }}
            formatter={(value) => [config.format(value as number), config.label]}
            labelFormatter={(_, payload) => payload?.[0]?.payload?.fullAddress || ''}
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
