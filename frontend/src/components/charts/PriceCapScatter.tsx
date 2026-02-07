'use client';

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from 'recharts';
import type { PropertyWithMetrics } from '@/lib/types';

interface PriceCapScatterProps {
  properties: PropertyWithMetrics[];
  className?: string;
}

const formatPrice = (price: number) => {
  if (price >= 1000000) return `$${(price / 1000000).toFixed(1)}M`;
  return `$${(price / 1000).toFixed(0)}K`;
};

export function PriceCapScatter({ properties, className }: PriceCapScatterProps) {
  const data = properties
    .filter((p) => p.metrics.cap_rate != null)
    .map((p) => ({
      price: p.listing.price,
      capRate: p.metrics.cap_rate,
      score: p.metrics.score,
      address: p.listing.address,
      type: p.listing.property_type,
    }));

  if (data.length === 0) {
    return (
      <div className={className}>
        <div className="flex items-center justify-center h-[300px] text-muted-foreground">
          No data available
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            type="number"
            dataKey="price"
            name="Price"
            tickFormatter={formatPrice}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            label={{
              value: 'Price',
              position: 'bottom',
              fill: 'hsl(var(--muted-foreground))',
            }}
          />
          <YAxis
            type="number"
            dataKey="capRate"
            name="Cap Rate"
            unit="%"
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            label={{
              value: 'Cap Rate %',
              angle: -90,
              position: 'insideLeft',
              fill: 'hsl(var(--muted-foreground))',
            }}
          />
          <ZAxis type="number" dataKey="score" range={[50, 400]} name="Score" />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--popover))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
            }}
            formatter={(value, name) => {
              const v = value as number;
              if (name === 'Price') return [formatPrice(v), name];
              if (name === 'Cap Rate') return [`${v.toFixed(2)}%`, name];
              return [v, name];
            }}
            labelFormatter={(_, payload) => {
              const item = payload?.[0]?.payload;
              return item ? `${item.address} (${item.type})` : '';
            }}
          />
          <Scatter
            name="Properties"
            data={data}
            fill="hsl(var(--primary))"
            fillOpacity={0.6}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
