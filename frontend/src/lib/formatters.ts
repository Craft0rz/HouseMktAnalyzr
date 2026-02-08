/**
 * Shared formatting utilities for consistent display across the app.
 * All formatters accept an optional locale parameter ('en' | 'fr').
 */

import type { Locale } from '@/i18n/LanguageContext';

const intlLocale = (locale: Locale = 'en') => locale === 'fr' ? 'fr-CA' : 'en-CA';

export const formatPrice = (price: number, locale: Locale = 'en'): string => {
  return new Intl.NumberFormat(intlLocale(locale), {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(price);
};

export const formatPercent = (value: number | null | undefined): string => {
  if (value == null) return '-';
  return `${value.toFixed(1)}%`;
};

export const formatCashFlow = (value: number | null | undefined, locale: Locale = 'en'): string => {
  if (value == null) return '-';
  const formatted = new Intl.NumberFormat(intlLocale(locale), {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(Math.abs(value));
  return value >= 0 ? formatted : `-${formatted}`;
};

export const formatNumber = (value: number | null | undefined, locale: Locale = 'en'): string => {
  if (value == null) return '-';
  return new Intl.NumberFormat(intlLocale(locale)).format(value);
};

export const formatDate = (dateString: string | null | undefined, locale: Locale = 'en'): string => {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString(intlLocale(locale), {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

export const getScoreColor = (score: number): string => {
  if (score >= 70) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
};
