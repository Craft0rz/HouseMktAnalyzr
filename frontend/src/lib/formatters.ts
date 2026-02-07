/**
 * Shared formatting utilities for consistent display across the app.
 */

export const formatPrice = (price: number): string => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(price);
};

export const formatPercent = (value: number | null | undefined): string => {
  if (value == null) return '-';
  return `${value.toFixed(1)}%`;
};

export const formatCashFlow = (value: number | null | undefined): string => {
  if (value == null) return '-';
  const formatted = new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(Math.abs(value));
  return value >= 0 ? formatted : `-${formatted}`;
};

export const formatNumber = (value: number | null | undefined): string => {
  if (value == null) return '-';
  return new Intl.NumberFormat('en-CA').format(value);
};

export const formatDate = (dateString: string | null | undefined): string => {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('en-CA', {
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

export const getPropertyTypeLabel = (type: string): string => {
  const labels: Record<string, string> = {
    DUPLEX: 'Duplex',
    TRIPLEX: 'Triplex',
    QUADPLEX: 'Quadplex',
    MULTIPLEX: '5+ Units',
    HOUSE: 'House',
  };
  return labels[type] || type;
};
