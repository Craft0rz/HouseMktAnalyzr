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
import { useTranslation } from '@/i18n/LanguageContext';

interface PriceCapScatterProps {
  properties: PropertyWithMetrics[];
  className?: string;
}

export function PriceCapScatter({ properties, className }: PriceCapScatterProps) {
  const { t, locale } = useTranslation();

  const formatPrice = (price: number) => {
    if (price >= 1000000) return `${(price / 1000000).toFixed(1)}M$`;
    return `${(price / 1000).toFixed(0)}K$`;
  };

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
          {t('chart.noData')}
        </div>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: typeof data[number] }> }) => {
    if (!active || !payload?.length) return null;
    const item = payload[0].payload;
    const priceFormatted = new Intl.NumberFormat(locale === 'fr' ? 'fr-CA' : 'en-CA', {
      style: 'currency', currency: 'CAD', maximumFractionDigits: 0,
    }).format(item.price);

    return (
      <div style={{
        backgroundColor: 'var(--popover)',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        color: 'var(--popover-foreground)',
        padding: '8px 12px',
        fontSize: '12px',
      }}>
        <p style={{ fontWeight: 600, marginBottom: 4 }}>{item.address}</p>
        <p style={{ opacity: 0.7, marginBottom: 4 }}>{item.type}</p>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
          <span>{t('chart.price')}</span>
          <span style={{ fontWeight: 500 }}>{priceFormatted}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
          <span>{t('chart.capRate')}</span>
          <span style={{ fontWeight: 500 }}>{item.capRate?.toFixed(2)}%</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
          <span>{t('chart.score')}</span>
          <span style={{ fontWeight: 500 }}>{item.score}</span>
        </div>
      </div>
    );
  };

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            type="number"
            dataKey="price"
            name={t('chart.price')}
            tickFormatter={formatPrice}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            label={{
              value: t('chart.price'),
              position: 'bottom',
              fill: 'var(--muted-foreground)',
            }}
          />
          <YAxis
            type="number"
            dataKey="capRate"
            name={t('chart.capRate')}
            unit="%"
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            label={{
              value: t('chart.capRateAxis'),
              angle: -90,
              position: 'insideLeft',
              fill: 'var(--muted-foreground)',
            }}
          />
          <ZAxis type="number" dataKey="score" range={[50, 400]} name={t('chart.score')} />
          <Tooltip content={<CustomTooltip />} />
          <Scatter
            name={t('chart.properties')}
            data={data}
            fill="var(--chart-1)"
            fillOpacity={0.6}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
