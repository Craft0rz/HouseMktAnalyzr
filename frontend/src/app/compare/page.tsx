'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import {
  BarChart3, X, ExternalLink, ArrowLeft, Loader2,
  Shield, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useComparison } from '@/lib/comparison-context';
import { ScoreBreakdown } from '@/components/charts';
import { useTranslation } from '@/i18n/LanguageContext';
import { formatPrice as formatPriceUtil } from '@/lib/formatters';
import { marketApi } from '@/lib/api';
import type {
  PropertyWithMetrics,
  MarketSummaryResponse,
  RentTrendResponse,
  DemographicProfile,
  NeighbourhoodResponse,
} from '@/lib/types';

const formatPercent = (value: number | null | undefined) => {
  if (value == null) return '-';
  return `${value.toFixed(2)}%`;
};

const getScoreColor = (score: number) => {
  if (score >= 70) return 'text-green-600';
  if (score >= 50) return 'text-yellow-600';
  return 'text-red-600';
};

const getCashFlowColor = (cf: number | null | undefined) => {
  if (cf == null) return '';
  return cf >= 0 ? 'text-green-600' : 'text-red-600';
};

const getSafetyColor = (v: unknown) => {
  if (v == null) return '';
  const n = v as number;
  return n >= 7 ? 'text-green-600' : n >= 4 ? 'text-yellow-600' : 'text-red-600';
};

const getRtiColor = (v: unknown) => {
  if (v == null) return '';
  const n = v as number;
  return n < 25 ? 'text-green-600' : n <= 30 ? 'text-yellow-600' : 'text-red-600';
};

// Helper to find best/worst values for highlighting
function getBestValue(
  properties: PropertyWithMetrics[],
  getValue: (p: PropertyWithMetrics) => number | null | undefined,
  higherIsBetter = true
) {
  const values = properties.map(getValue).filter((v) => v != null) as number[];
  if (values.length === 0) return null;
  return higherIsBetter ? Math.max(...values) : Math.min(...values);
}

// Score breakdown key → i18n key mapping
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

interface PropertyMarketData {
  rentTrend: RentTrendResponse | null;
  demographics: DemographicProfile | null;
  neighbourhood: NeighbourhoodResponse | null;
}

interface CompareRowProps {
  label: string;
  properties: PropertyWithMetrics[];
  getValue: (p: PropertyWithMetrics) => string | number | boolean | null | undefined;
  format?: (value: unknown) => string;
  getBest?: (properties: PropertyWithMetrics[]) => number | null;
  getNumericValue?: (p: PropertyWithMetrics) => number | null | undefined;
  colorFn?: (value: unknown) => string;
  bestLabel?: string;
}

function CompareRow({
  label,
  properties,
  getValue,
  format = (v) => String(v ?? '-'),
  getBest,
  getNumericValue,
  colorFn,
  bestLabel = 'Best',
}: CompareRowProps) {
  const bestValue = getBest ? getBest(properties) : null;

  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: `200px repeat(${properties.length}, 1fr)` }}>
      <div className="text-sm text-muted-foreground py-2">{label}</div>
      {properties.map((p) => {
        const value = getValue(p);
        const numValue = getNumericValue ? getNumericValue(p) : null;
        const isBest = bestValue !== null && numValue === bestValue;
        const colorClass = colorFn ? colorFn(value) : '';

        return (
          <div
            key={p.listing.id}
            className={`text-sm py-2 font-medium ${colorClass} ${isBest ? 'bg-green-50 dark:bg-green-950 px-2 rounded' : ''}`}
          >
            {format(value)}
            {isBest && <Badge variant="outline" className="ml-2 text-xs">{bestLabel}</Badge>}
          </div>
        );
      })}
    </div>
  );
}

export default function ComparePage() {
  const { selectedProperties, removeProperty, clearAll } = useComparison();
  const { t, locale } = useTranslation();
  const formatPrice = (price: number) => formatPriceUtil(price, locale);

  // Market data state
  const [marketDataMap, setMarketDataMap] = useState<Record<string, PropertyMarketData>>({});
  const [marketSummary, setMarketSummary] = useState<MarketSummaryResponse | null>(null);
  const [marketLoading, setMarketLoading] = useState(false);

  // Stable dependency for useEffect
  const propertyIds = useMemo(
    () => selectedProperties.map((p) => p.listing.id).sort().join(','),
    [selectedProperties]
  );

  // Fetch market data for all selected properties
  useEffect(() => {
    if (selectedProperties.length === 0) {
      setMarketDataMap({});
      setMarketSummary(null);
      return;
    }

    setMarketLoading(true);

    // Shared market rates (same for all properties)
    marketApi.summary().then(setMarketSummary).catch(() => {});

    // Per-property location data
    Promise.all(
      selectedProperties.map(async (p) => {
        const city = p.listing.city || 'Montreal';
        const bedrooms = Math.min(p.listing.bedrooms || 2, 3);
        const estRent = p.listing.estimated_rent || p.metrics.estimated_monthly_rent;
        const perUnitRent = Math.round(estRent / (p.listing.units || 1));
        const assessment = p.listing.municipal_assessment || undefined;

        const [rentTrend, demographics, neighbourhood] = await Promise.all([
          marketApi.rentTrend(city, bedrooms).catch(() =>
            city !== 'Montreal CMA Total'
              ? marketApi.rentTrend('Montreal CMA Total', bedrooms).catch(() => null)
              : null
          ),
          marketApi.demographics(city, perUnitRent).catch(() => null),
          marketApi.neighbourhood(city, assessment).catch(() => null),
        ]);

        return [p.listing.id, { rentTrend, demographics, neighbourhood }] as const;
      })
    ).then((results) => {
      const map: Record<string, PropertyMarketData> = {};
      for (const [id, data] of results) {
        map[id] = data;
      }
      setMarketDataMap(map);
      setMarketLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyIds]);

  if (selectedProperties.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('compare.title')}</h1>
          <p className="text-muted-foreground">
            {t('compare.subtitle')}
          </p>
        </div>

        <Card>
          <CardHeader>
            <BarChart3 className="h-10 w-10 text-muted-foreground" />
            <CardTitle className="mt-4">{t('compare.noProperties')}</CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription className="mb-4">
              {t('compare.noPropertiesDesc')}
            </CardDescription>
            <Button asChild>
              <Link href="/search">
                <ArrowLeft className="mr-2 h-4 w-4" />
                {t('compare.goToSearch')}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Helper: check if any property has a given market data field
  const anyHas = (fn: (d: PropertyMarketData) => unknown) =>
    selectedProperties.some((p) => {
      const d = marketDataMap[p.listing.id];
      return d != null && fn(d) != null;
    });

  const hasRentalRows =
    anyHas((d) => d.rentTrend?.current_rent) ||
    anyHas((d) => d.rentTrend?.vacancy_rate) ||
    anyHas((d) => d.rentTrend?.cagr_5yr ?? d.rentTrend?.annual_growth_rate);

  const hasNeighbourhoodRows =
    anyHas((d) => d.neighbourhood?.safety_score) ||
    anyHas((d) => d.demographics?.median_household_income) ||
    anyHas((d) => d.demographics?.rent_to_income_ratio) ||
    anyHas((d) => d.neighbourhood?.tax?.annual_tax_estimate);

  const hasGentrification = selectedProperties.some((p) => {
    const sig = marketDataMap[p.listing.id]?.neighbourhood?.gentrification_signal;
    return sig != null && sig !== 'none';
  });

  const hasLocationData = !marketLoading && Object.keys(marketDataMap).length > 0 &&
    (hasRentalRows || hasNeighbourhoodRows || hasGentrification);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('compare.title')}</h1>
          <p className="text-muted-foreground">
            {t('compare.comparing', { count: selectedProperties.length })}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={clearAll}>
            {t('common.clearAll')}
          </Button>
          <Button asChild variant="outline">
            <Link href="/search">
              {t('common.addMore')}
            </Link>
          </Button>
        </div>
      </div>

      {/* Property Headers */}
      <div className="grid gap-4" style={{ gridTemplateColumns: `200px repeat(${selectedProperties.length}, 1fr)` }}>
        <div />
        {selectedProperties.map((p) => (
          <Card key={p.listing.id} className="relative">
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2 h-6 w-6 p-0"
              onClick={() => removeProperty(p.listing.id)}
            >
              <X className="h-4 w-4" />
            </Button>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Badge variant="outline">
                  {t('propertyTypes.' + p.listing.property_type)}
                </Badge>
              </div>
              <CardTitle className="text-lg truncate pr-8">{p.listing.address}</CardTitle>
              <CardDescription>{p.listing.city}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatPrice(p.listing.price)}</div>
              <div className={`text-3xl font-bold mt-2 ${getScoreColor(p.metrics.score)}`}>
                {p.metrics.score.toFixed(0)}
                <span className="text-sm font-normal text-muted-foreground ml-1">{t('common.score')}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Property Details */}
      <Card>
        <CardHeader>
          <CardTitle>{t('compare.propertyDetails')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <CompareRow
            label={t('compare.units')}
            properties={selectedProperties}
            getValue={(p) => p.listing.units}
            bestLabel={t('common.best')}
          />
          <CompareRow
            label={t('compare.bedrooms')}
            properties={selectedProperties}
            getValue={(p) => p.listing.bedrooms}
            bestLabel={t('common.best')}
          />
          <CompareRow
            label={t('compare.bathrooms')}
            properties={selectedProperties}
            getValue={(p) => p.listing.bathrooms}
            bestLabel={t('common.best')}
          />
          <CompareRow
            label={t('compare.squareFeet')}
            properties={selectedProperties}
            getValue={(p) => p.listing.sqft}
            format={(v) => (v ? t('compare.sqft', { value: Number(v).toLocaleString() }) : '-')}
            bestLabel={t('common.best')}
          />
          <CompareRow
            label={t('compare.yearBuilt')}
            properties={selectedProperties}
            getValue={(p) => p.listing.year_built}
            bestLabel={t('common.best')}
          />
        </CardContent>
      </Card>

      {/* Financial Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>{t('compare.financialMetrics')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <CompareRow
            label={t('compare.pricePerUnit')}
            properties={selectedProperties}
            getValue={(p) => p.metrics.price_per_unit}
            format={(v) => formatPrice(v as number)}
            getBest={(props) => getBestValue(props, (p) => p.metrics.price_per_unit, false)}
            getNumericValue={(p) => p.metrics.price_per_unit}
            bestLabel={t('common.best')}
          />
          <CompareRow
            label={t('compare.estMonthlyRent')}
            properties={selectedProperties}
            getValue={(p) => p.metrics.estimated_monthly_rent}
            format={(v) => formatPrice(v as number)}
            getBest={(props) => getBestValue(props, (p) => p.metrics.estimated_monthly_rent, true)}
            getNumericValue={(p) => p.metrics.estimated_monthly_rent}
            bestLabel={t('common.best')}
          />
          <Separator className="my-2" />
          <CompareRow
            label={t('compare.capRate')}
            properties={selectedProperties}
            getValue={(p) => p.metrics.cap_rate}
            format={(v) => formatPercent(v as number | null)}
            getBest={(props) => getBestValue(props, (p) => p.metrics.cap_rate, true)}
            getNumericValue={(p) => p.metrics.cap_rate}
            bestLabel={t('common.best')}
          />
          <CompareRow
            label={t('compare.grossYield')}
            properties={selectedProperties}
            getValue={(p) => p.metrics.gross_rental_yield}
            format={(v) => formatPercent(v as number | null)}
            getBest={(props) => getBestValue(props, (p) => p.metrics.gross_rental_yield, true)}
            getNumericValue={(p) => p.metrics.gross_rental_yield}
            bestLabel={t('common.best')}
          />
          <Separator className="my-2" />
          <CompareRow
            label={t('compare.monthlyCashFlow')}
            properties={selectedProperties}
            getValue={(p) => p.metrics.cash_flow_monthly}
            format={(v) => (v != null ? formatPrice(v as number) : '-')}
            getBest={(props) => getBestValue(props, (p) => p.metrics.cash_flow_monthly, true)}
            getNumericValue={(p) => p.metrics.cash_flow_monthly}
            colorFn={(v) => getCashFlowColor(v as number | null)}
            bestLabel={t('common.best')}
          />
          <CompareRow
            label={t('compare.cashFlowStatus')}
            properties={selectedProperties}
            getValue={(p) => p.metrics.is_positive_cash_flow}
            format={(v) => (
              v ? t('compare.positiveStatus') : t('compare.negativeStatus')
            )}
            colorFn={(v) => (v ? 'text-green-600' : 'text-red-600')}
            bestLabel={t('common.best')}
          />
        </CardContent>
      </Card>

      {/* Location Intelligence */}
      {marketLoading && (
        <Card>
          <CardContent className="py-6">
            <div className="flex items-center gap-3 justify-center text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">{t('compare.loadingMarketData')}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {hasLocationData && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              {t('compare.locationIntelligence')}
            </CardTitle>
            <CardDescription>{t('compare.locationIntelligenceDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {/* --- Rental Market --- */}
            {anyHas((d) => d.rentTrend?.current_rent) && (
              <CompareRow
                label={t('compare.marketRent')}
                properties={selectedProperties}
                getValue={(p) => marketDataMap[p.listing.id]?.rentTrend?.current_rent}
                format={(v) => v != null ? `${formatPrice(v as number)}/${t('common.perMonth')}` : '-'}
                bestLabel={t('common.best')}
              />
            )}

            {anyHas((d) => d.rentTrend?.vacancy_rate) && (
              <CompareRow
                label={t('compare.vacancyRate')}
                properties={selectedProperties}
                getValue={(p) => marketDataMap[p.listing.id]?.rentTrend?.vacancy_rate}
                format={(v) => v != null ? `${(v as number).toFixed(1)}%` : '-'}
                getBest={(props) => getBestValue(props, (p) => marketDataMap[p.listing.id]?.rentTrend?.vacancy_rate, false)}
                getNumericValue={(p) => marketDataMap[p.listing.id]?.rentTrend?.vacancy_rate}
                bestLabel={t('common.best')}
              />
            )}

            {anyHas((d) => d.rentTrend?.cagr_5yr ?? d.rentTrend?.annual_growth_rate) && (
              <CompareRow
                label={t('compare.rentGrowth')}
                properties={selectedProperties}
                getValue={(p) => {
                  const rt = marketDataMap[p.listing.id]?.rentTrend;
                  return rt?.cagr_5yr ?? rt?.annual_growth_rate;
                }}
                format={(v) => v != null ? `${(v as number) > 0 ? '+' : ''}${(v as number).toFixed(1)}%` : '-'}
                getBest={(props) => getBestValue(props, (p) => {
                  const rt = marketDataMap[p.listing.id]?.rentTrend;
                  return rt?.cagr_5yr ?? rt?.annual_growth_rate;
                }, true)}
                getNumericValue={(p) => {
                  const rt = marketDataMap[p.listing.id]?.rentTrend;
                  return rt?.cagr_5yr ?? rt?.annual_growth_rate;
                }}
                bestLabel={t('common.best')}
              />
            )}

            {/* Separator between rental & neighbourhood groups */}
            {hasRentalRows && hasNeighbourhoodRows && <Separator className="my-2" />}

            {/* --- Neighbourhood & Demographics --- */}
            {anyHas((d) => d.neighbourhood?.safety_score) && (
              <CompareRow
                label={t('compare.safetyScore')}
                properties={selectedProperties}
                getValue={(p) => marketDataMap[p.listing.id]?.neighbourhood?.safety_score}
                format={(v) => v != null ? `${(v as number).toFixed(1)}/10` : '-'}
                getBest={(props) => getBestValue(props, (p) => marketDataMap[p.listing.id]?.neighbourhood?.safety_score, true)}
                getNumericValue={(p) => marketDataMap[p.listing.id]?.neighbourhood?.safety_score}
                colorFn={getSafetyColor}
                bestLabel={t('common.best')}
              />
            )}

            {anyHas((d) => d.demographics?.median_household_income) && (
              <CompareRow
                label={t('compare.medianIncome')}
                properties={selectedProperties}
                getValue={(p) => marketDataMap[p.listing.id]?.demographics?.median_household_income}
                format={(v) => v != null ? formatPrice(v as number) : '-'}
                getBest={(props) => getBestValue(props, (p) => marketDataMap[p.listing.id]?.demographics?.median_household_income, true)}
                getNumericValue={(p) => marketDataMap[p.listing.id]?.demographics?.median_household_income}
                bestLabel={t('common.best')}
              />
            )}

            {anyHas((d) => d.demographics?.rent_to_income_ratio) && (
              <CompareRow
                label={t('compare.rentToIncome')}
                properties={selectedProperties}
                getValue={(p) => marketDataMap[p.listing.id]?.demographics?.rent_to_income_ratio}
                format={(v) => v != null ? `${(v as number).toFixed(1)}%` : '-'}
                getBest={(props) => getBestValue(props, (p) => marketDataMap[p.listing.id]?.demographics?.rent_to_income_ratio, false)}
                getNumericValue={(p) => marketDataMap[p.listing.id]?.demographics?.rent_to_income_ratio}
                colorFn={getRtiColor}
                bestLabel={t('common.best')}
              />
            )}

            {anyHas((d) => d.neighbourhood?.tax?.annual_tax_estimate) && (
              <CompareRow
                label={t('compare.estAnnualTax')}
                properties={selectedProperties}
                getValue={(p) => marketDataMap[p.listing.id]?.neighbourhood?.tax?.annual_tax_estimate}
                format={(v) => v != null ? formatPrice(v as number) : '-'}
                getBest={(props) => getBestValue(props, (p) => marketDataMap[p.listing.id]?.neighbourhood?.tax?.annual_tax_estimate, false)}
                getNumericValue={(p) => marketDataMap[p.listing.id]?.neighbourhood?.tax?.annual_tax_estimate}
                bestLabel={t('common.best')}
              />
            )}

            {/* Gentrification signal */}
            {hasGentrification && (
              <>
                <Separator className="my-2" />
                <CompareRow
                  label={t('compare.gentrification')}
                  properties={selectedProperties}
                  getValue={(p) => marketDataMap[p.listing.id]?.neighbourhood?.gentrification_signal}
                  format={(v) => {
                    if (v === 'early') return t('compare.earlyStage');
                    if (v === 'mid') return t('compare.midStage');
                    if (v === 'mature') return t('compare.mature');
                    return '-';
                  }}
                  bestLabel={t('common.best')}
                />
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Score Breakdown - Visual */}
      <Card>
        <CardHeader>
          <CardTitle>{t('compare.scoreBreakdown')}</CardTitle>
          <CardDescription>{t('compare.scoreBreakdownDesc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: `repeat(${selectedProperties.length}, 1fr)` }}
          >
            {selectedProperties.map((p) => (
              <div key={p.listing.id} className="text-center">
                <p className="text-sm font-medium mb-2 truncate">
                  {p.listing.address.split(',')[0]}
                </p>
                <ScoreBreakdown scoreBreakdown={p.metrics.score_breakdown} />
                <p className={`text-2xl font-bold mt-2 ${getScoreColor(p.metrics.score)}`}>
                  {p.metrics.score.toFixed(0)}
                </p>
              </div>
            ))}
          </div>
          <Separator className="my-4" />
          {Object.keys(selectedProperties[0]?.metrics.score_breakdown || {}).map((key) => (
            <CompareRow
              key={key}
              label={t(SCORE_LABEL_MAP[key] || key)}
              properties={selectedProperties}
              getValue={(p) => p.metrics.score_breakdown[key]}
              format={(v) => t('compare.pts', { value: (v as number).toFixed(1) })}
              getBest={(props) => getBestValue(props, (p) => p.metrics.score_breakdown[key], true)}
              getNumericValue={(p) => p.metrics.score_breakdown[key]}
              bestLabel={t('common.best')}
            />
          ))}
          <Separator className="my-2" />
          <CompareRow
            label={t('compare.totalScore')}
            properties={selectedProperties}
            getValue={(p) => p.metrics.score}
            format={(v) => `${(v as number).toFixed(0)}`}
            getBest={(props) => getBestValue(props, (p) => p.metrics.score, true)}
            getNumericValue={(p) => p.metrics.score}
            colorFn={(v) => getScoreColor(v as number)}
            bestLabel={t('common.best')}
          />
        </CardContent>
      </Card>

      {/* Market Context - shared rates banner */}
      {marketSummary && (marketSummary.mortgage_rate != null || marketSummary.policy_rate != null) && (
        <div className="rounded-lg border bg-muted/30 p-4">
          <div className="flex items-center gap-6 flex-wrap text-sm">
            <span className="font-medium text-muted-foreground">{t('compare.marketContext')}</span>
            {marketSummary.mortgage_rate != null && (
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground">{t('compare.mortgageRate5yr')}</span>
                <span className="font-bold">{marketSummary.mortgage_rate.toFixed(2)}%</span>
                {marketSummary.mortgage_direction === 'up' ? (
                  <TrendingUp className="h-3 w-3 text-red-500" />
                ) : marketSummary.mortgage_direction === 'down' ? (
                  <TrendingDown className="h-3 w-3 text-green-500" />
                ) : (
                  <Minus className="h-3 w-3 text-muted-foreground" />
                )}
              </div>
            )}
            {marketSummary.policy_rate != null && (
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground">{t('compare.policyRate')}</span>
                <span className="font-bold">{marketSummary.policy_rate.toFixed(2)}%</span>
                {marketSummary.policy_direction === 'up' ? (
                  <TrendingUp className="h-3 w-3 text-red-500" />
                ) : marketSummary.policy_direction === 'down' ? (
                  <TrendingDown className="h-3 w-3 text-green-500" />
                ) : (
                  <Minus className="h-3 w-3 text-muted-foreground" />
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Links */}
      <div className="grid gap-4" style={{ gridTemplateColumns: `200px repeat(${selectedProperties.length}, 1fr)` }}>
        <div />
        {selectedProperties.map((p) => (
          <Button key={p.listing.id} asChild variant="outline">
            <a href={p.listing.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" />
              {t('compare.viewOnCentris')}
            </a>
          </Button>
        ))}
      </div>
    </div>
  );
}
