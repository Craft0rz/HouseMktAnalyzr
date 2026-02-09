'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { ScrapeJob } from '@/lib/types';
import { useTranslation } from '@/i18n/LanguageContext';

interface QualityTrendProps {
  jobs: ScrapeJob[];
}

const tooltipStyle = {
  backgroundColor: 'var(--popover)',
  border: '1px solid var(--border)',
  borderRadius: '6px',
  color: 'var(--popover-foreground)',
  padding: '8px 12px',
  fontSize: '12px',
};

function formatDate(dateStr: string | null, locale: string): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString(locale === 'fr' ? 'fr-CA' : 'en-CA', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function QualityTrendChart({ jobs }: QualityTrendProps) {
  const { t, locale } = useTranslation();

  const data = jobs
    .filter((j) => j.status === 'completed' && j.quality_snapshot)
    .sort((a, b) => new Date(a.completed_at!).getTime() - new Date(b.completed_at!).getTime())
    .map((j) => ({
      date: formatDate(j.completed_at, locale),
      avg_score: j.quality_snapshot!.avg_score,
      high_quality: j.quality_snapshot!.high_quality,
      low_quality: j.quality_snapshot!.low_quality,
    }));

  if (data.length < 2) return null;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="date"
          tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
          tickLine={{ stroke: 'var(--border)' }}
        />
        <YAxis
          tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
          tickLine={{ stroke: 'var(--border)' }}
        />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend />
        <Line
          type="monotone"
          dataKey="avg_score"
          name={t('status.avgScore')}
          stroke="var(--chart-1)"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          type="monotone"
          dataKey="high_quality"
          name={t('status.highQuality')}
          stroke="var(--chart-2)"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          type="monotone"
          dataKey="low_quality"
          name={t('status.lowQuality')}
          stroke="var(--chart-5)"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function EnrichmentTrendChart({ jobs }: QualityTrendProps) {
  const { t, locale } = useTranslation();

  const data = jobs
    .filter((j) => j.status === 'completed' && j.quality_snapshot?.enrichment_rates)
    .sort((a, b) => new Date(a.completed_at!).getTime() - new Date(b.completed_at!).getTime())
    .map((j) => {
      const rates = j.quality_snapshot!.enrichment_rates!;
      return {
        date: formatDate(j.completed_at, locale),
        details: rates.details,
        walk_scores: rates.walk_scores,
        photos: rates.photos,
        conditions: rates.conditions,
      };
    });

  if (data.length < 2) return null;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="date"
          tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
          tickLine={{ stroke: 'var(--border)' }}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
          tickLine={{ stroke: 'var(--border)' }}
          tickFormatter={(v) => `${v}%`}
        />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value) => `${value}%`}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="details"
          name={t('status.phaseEnrichDetails')}
          stroke="var(--chart-1)"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          type="monotone"
          dataKey="walk_scores"
          name={t('status.phaseEnrichWalkScores')}
          stroke="var(--chart-2)"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          type="monotone"
          dataKey="photos"
          name={t('status.phaseEnrichPhotos')}
          stroke="var(--chart-3)"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          type="monotone"
          dataKey="conditions"
          name={t('status.phaseEnrichConditions')}
          stroke="var(--chart-4)"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
