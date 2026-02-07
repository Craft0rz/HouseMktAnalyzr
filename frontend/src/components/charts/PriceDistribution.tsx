'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { PropertyWithMetrics } from '@/lib/types';

interface PriceDistributionProps {
  properties: PropertyWithMetrics[];
  className?: string;
}

const formatPrice = (price: number) => {
  if (price >= 1000000) return `$${(price / 1000000).toFixed(1)}M`;
  return `$${(price / 1000).toFixed(0)}K`;
};

export function PriceDistribution({ properties, className }: PriceDistributionProps) {
  // Create price buckets
  const buckets = [
    { min: 0, max: 300000, label: '<$300K' },
    { min: 300000, max: 400000, label: '$300-400K' },
    { min: 400000, max: 500000, label: '$400-500K' },
    { min: 500000, max: 600000, label: '$500-600K' },
    { min: 600000, max: 750000, label: '$600-750K' },
    { min: 750000, max: 1000000, label: '$750K-1M' },
    { min: 1000000, max: Infinity, label: '>$1M' },
  ];

  const data = buckets.map((bucket) => {
    const count = properties.filter(
      (p) => p.listing.price >= bucket.min && p.listing.price < bucket.max
    ).length;
    const avgScore =
      properties
        .filter((p) => p.listing.price >= bucket.min && p.listing.price < bucket.max)
        .reduce((sum, p) => sum + p.metrics.score, 0) / (count || 1);

    return {
      range: bucket.label,
      count,
      avgScore: count > 0 ? Math.round(avgScore) : 0,
    };
  });

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="range"
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
          />
          <YAxis
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            label={{
              value: 'Count',
              angle: -90,
              position: 'insideLeft',
              fill: 'hsl(var(--muted-foreground))',
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--popover))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
            }}
            formatter={(value, name) => {
              if (name === 'count') return [value, 'Properties'];
              if (name === 'avgScore') return [value, 'Avg Score'];
              return [value, name];
            }}
          />
          <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
