'use client';

import { useState, useEffect } from 'react';
import {
  Building2,
  TrendingUp,
  TrendingDown,
  Calculator,
  Search,
  Minus,
  Landmark,
  ChevronRight,
  Home as HomeIcon,
  ExternalLink,
} from 'lucide-react';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { LoadingCard } from '@/components/LoadingCard';
import { useTopOpportunities } from '@/hooks/useProperties';
import { MetricsBar, PriceCapScatter } from '@/components/charts';
import { PropertyDetail } from '@/components/PropertyDetail';
import { formatPrice, formatCashFlow, getScoreColor } from '@/lib/formatters';
import { marketApi } from '@/lib/api';
import type { MarketSummaryResponse, PropertyWithMetrics } from '@/lib/types';
import { useTranslation } from '@/i18n/LanguageContext';

export default function Home() {
  const { t, locale } = useTranslation();
  const [region, setRegion] = useState('montreal');
  const [marketData, setMarketData] = useState<MarketSummaryResponse | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<PropertyWithMetrics | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const handlePropertyClick = (property: PropertyWithMetrics) => {
    setSelectedProperty(property);
    setDetailOpen(true);
  };
  const { data: topOpportunities, isLoading } = useTopOpportunities(
    { region, limit: 10, min_score: 50 },
    true
  );

  const REGIONS = [
    { value: 'montreal', label: t('regions.montreal') },
    { value: 'laval', label: t('regions.laval') },
    { value: 'south-shore', label: t('regions.southShore') },
    { value: 'north-shore', label: t('regions.northShore') },
    { value: 'laurentides', label: t('regions.laurentides') },
    { value: 'lanaudiere', label: t('regions.lanaudiere') },
  ];

  useEffect(() => {
    marketApi.summary().then(setMarketData).catch(() => {});
  }, []);

  const properties = topOpportunities?.results || [];
  const hasData = properties.length > 0;

  const summary = topOpportunities?.summary;

  return (
    <div className="space-y-6">
      {/* Page Header: title, region selector, rates — all in one row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('home.topOpportunities')}</h1>
          <p className="text-sm text-muted-foreground">{t('home.marketOverviewDesc')}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Rates pills */}
          {marketData && marketData.mortgage_rate != null && (
            <div className="hidden md:flex items-center gap-4 text-xs text-muted-foreground border rounded-lg px-3 py-1.5">
              <Landmark className="h-3 w-3 shrink-0" />
              <div className="flex items-center gap-1">
                <span>{t('home.mortgageRate')}</span>
                <span className="font-bold text-foreground tabular-nums">{marketData.mortgage_rate.toFixed(2)}%</span>
                {marketData.mortgage_direction === 'down' ? (
                  <TrendingDown className="h-3 w-3 text-emerald-500" />
                ) : marketData.mortgage_direction === 'up' ? (
                  <TrendingUp className="h-3 w-3 text-red-500" />
                ) : (
                  <Minus className="h-3 w-3" />
                )}
              </div>
              {marketData.policy_rate != null && (
                <div className="flex items-center gap-1">
                  <span>{t('home.policyRate')}</span>
                  <span className="font-bold text-foreground tabular-nums">{marketData.policy_rate.toFixed(2)}%</span>
                  {marketData.policy_direction === 'down' ? (
                    <TrendingDown className="h-3 w-3 text-emerald-500" />
                  ) : marketData.policy_direction === 'up' ? (
                    <TrendingUp className="h-3 w-3 text-red-500" />
                  ) : (
                    <Minus className="h-3 w-3" />
                  )}
                </div>
              )}
            </div>
          )}
          <Select value={region} onValueChange={setRegion}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder={t('regions.selectRegion')} />
            </SelectTrigger>
            <SelectContent>
              {REGIONS.map((r) => (
                <SelectItem key={r.value} value={r.value}>
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Main content */}
      {isLoading ? (
        <LoadingCard message={t('home.loadingMarket')} description={t('home.loadingMarketDesc')} />
      ) : hasData ? (
        <>
          {/* Summary KPIs — compact inline bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-lg border bg-card px-4 py-3">
              <p className="text-[11px] text-muted-foreground uppercase tracking-wider">{t('home.propertiesAnalyzed')}</p>
              <p className="text-2xl font-bold tabular-nums mt-0.5">{summary?.total_analyzed ?? properties.length}</p>
            </div>
            <div className="rounded-lg border bg-card px-4 py-3">
              <p className="text-[11px] text-muted-foreground uppercase tracking-wider">{t('home.avgScore')}</p>
              <p className="text-2xl font-bold tabular-nums mt-0.5">
                {Math.round(summary?.avg_score ?? properties.reduce((s, p) => s + p.metrics.score, 0) / properties.length)}
                <span className="text-sm text-muted-foreground font-normal">/100</span>
              </p>
            </div>
            <div className="rounded-lg border bg-card px-4 py-3">
              <p className="text-[11px] text-muted-foreground uppercase tracking-wider">{t('home.avgCapRate')}</p>
              <p className="text-2xl font-bold tabular-nums mt-0.5">
                {(summary?.avg_cap_rate ?? properties.filter(p => p.metrics.cap_rate != null).reduce((s, p) => s + (p.metrics.cap_rate || 0), 0) / (properties.filter(p => p.metrics.cap_rate != null).length || 1)).toFixed(1)}
                <span className="text-sm text-muted-foreground font-normal">%</span>
              </p>
            </div>
            <div className="rounded-lg border bg-card px-4 py-3">
              <p className="text-[11px] text-muted-foreground uppercase tracking-wider">{t('home.positiveCashFlow')}</p>
              <p className="text-2xl font-bold tabular-nums mt-0.5">
                {summary?.positive_cash_flow_count ?? properties.filter(p => p.metrics.is_positive_cash_flow).length}
                <span className="text-sm text-muted-foreground font-normal">/{summary?.total_analyzed ?? properties.length}</span>
              </p>
            </div>
          </div>

          {/* Top 10 Comparison Table */}
          <Card>
            <CardHeader className="pb-0 pt-4 px-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">
                  {t('home.topOpportunities')}
                </CardTitle>
                <Button variant="ghost" size="sm" asChild className="text-xs h-7 gap-1">
                  <Link href="/search">
                    {t('home.fullSearch')}
                    <ChevronRight className="h-3 w-3" />
                  </Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-xs text-muted-foreground">
                      <th className="text-left font-medium px-4 py-2 w-8">#</th>
                      <th className="text-left font-medium px-2 py-2 w-12">{t('table.score')}</th>
                      <th className="text-left font-medium px-2 py-2">{t('table.address')}</th>
                      <th className="text-left font-medium px-2 py-2 hidden lg:table-cell">{t('table.type')}</th>
                      <th className="text-right font-medium px-2 py-2">{t('table.price')}</th>
                      <th className="text-right font-medium px-2 py-2 hidden sm:table-cell">{t('table.units')}</th>
                      <th className="text-right font-medium px-2 py-2 hidden md:table-cell">{t('table.pricePerUnit')}</th>
                      <th className="text-right font-medium px-2 py-2">{t('table.capRate')}</th>
                      <th className="text-right font-medium px-2 py-2">{t('table.cashFlow')}</th>
                      <th className="text-right font-medium px-2 py-2 hidden lg:table-cell">{t('table.yield')}</th>
                      <th className="text-center font-medium px-2 py-2 w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {properties.map((property, index) => (
                      <tr
                        key={property.listing.id}
                        className="border-b last:border-0 hover:bg-muted/50 transition-colors cursor-pointer"
                        onClick={() => handlePropertyClick(property)}
                      >
                        <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">{index + 1}</td>
                        <td className="px-2 py-2.5">
                          <div
                            className={`w-8 h-8 rounded-md flex items-center justify-center text-white text-xs font-bold ${getScoreColor(property.metrics.score)}`}
                          >
                            {property.metrics.score}
                          </div>
                        </td>
                        <td className="px-2 py-2.5">
                          <Link href={`/search?id=${property.listing.id}`} className="hover:underline">
                            <span className="font-medium">{property.listing.address.split(',')[0]}</span>
                          </Link>
                          <span className="text-xs text-muted-foreground block">
                            {property.listing.city}
                          </span>
                        </td>
                        <td className="px-2 py-2.5 hidden lg:table-cell">
                          <Badge variant="secondary" className="text-[10px] font-normal">
                            {property.listing.property_type}
                          </Badge>
                        </td>
                        <td className="px-2 py-2.5 text-right font-medium tabular-nums">
                          {formatPrice(property.listing.price, locale)}
                        </td>
                        <td className="px-2 py-2.5 text-right tabular-nums hidden sm:table-cell">
                          {property.listing.units}
                        </td>
                        <td className="px-2 py-2.5 text-right tabular-nums text-muted-foreground hidden md:table-cell">
                          {formatPrice(property.metrics.price_per_unit, locale)}
                        </td>
                        <td className="px-2 py-2.5 text-right font-medium tabular-nums">
                          {property.metrics.cap_rate != null ? `${property.metrics.cap_rate.toFixed(1)}%` : '-'}
                        </td>
                        <td className={`px-2 py-2.5 text-right font-medium tabular-nums ${
                          property.metrics.is_positive_cash_flow
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-red-600 dark:text-red-400'
                        }`}>
                          {property.metrics.cash_flow_monthly != null
                            ? formatCashFlow(property.metrics.cash_flow_monthly, locale)
                            : '-'}
                        </td>
                        <td className="px-2 py-2.5 text-right tabular-nums text-muted-foreground hidden lg:table-cell">
                          {property.metrics.gross_rental_yield != null
                            ? `${property.metrics.gross_rental_yield.toFixed(1)}%`
                            : '-'}
                        </td>
                        <td className="px-2 py-2.5 text-center">
                          {property.listing.url && (
                            <a
                              href={property.listing.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-muted-foreground hover:text-foreground transition-colors"
                              aria-label="View on Centris"
                            >
                              <ExternalLink className="h-3.5 w-3.5 inline" />
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Comparison Charts — score & cap rate side by side */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">{t('home.topByScore')}</CardTitle>
              </CardHeader>
              <CardContent>
                <MetricsBar properties={properties} metric="score" onBarClick={handlePropertyClick} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">{t('home.capRateComparison')}</CardTitle>
              </CardHeader>
              <CardContent>
                <MetricsBar properties={properties} metric="cap_rate" onBarClick={handlePropertyClick} />
              </CardContent>
            </Card>
          </div>

          {/* Price vs Cap scatter + Cash Flow comparison */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">{t('home.priceVsCap')}</CardTitle>
                <CardDescription className="text-xs">{t('home.bubbleSize')}</CardDescription>
              </CardHeader>
              <CardContent>
                <PriceCapScatter properties={properties} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">{t('home.cashFlowComparison')}</CardTitle>
              </CardHeader>
              <CardContent>
                <MetricsBar properties={properties} metric="cash_flow" onBarClick={handlePropertyClick} />
              </CardContent>
            </Card>
          </div>

          {/* Quick nav to other tools */}
          <div className="flex flex-wrap gap-2 pt-2">
            <Button variant="outline" size="sm" asChild>
              <Link href="/search">
                <Search className="mr-1.5 h-3.5 w-3.5" />
                {t('home.fullSearch')}
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href="/calculator">
                <Calculator className="mr-1.5 h-3.5 w-3.5" />
                {t('home.quickCalculator')}
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href="/compare">
                <Building2 className="mr-1.5 h-3.5 w-3.5" />
                {t('home.featureCompare')}
              </Link>
            </Button>
          </div>
        </>
      ) : (
        /* Empty / Getting Started State */
        <Card className="border-dashed">
          <CardContent className="py-12">
            <div className="text-center space-y-4 max-w-md mx-auto">
              <div className="inline-flex p-3 rounded-full bg-muted">
                <HomeIcon className="h-6 w-6 text-muted-foreground" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">{t('home.gettingStarted')}</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('home.gettingStartedDesc')}
                </p>
              </div>
              <div className="text-left">
                <p className="text-xs text-muted-foreground mb-2">{t('home.startBackend')}</p>
                <pre className="bg-muted/70 dark:bg-muted/50 p-4 rounded-lg text-xs overflow-x-auto font-mono">
                  <code>
                    cd HouseMktAnalyzr{'\n'}
                    set PYTHONPATH=src{'\n'}
                    python -m uvicorn backend.app.main:app --reload
                  </code>
                </pre>
                <p className="text-xs text-muted-foreground mt-3">
                  {t('home.apiDocs')}{' '}
                  <a
                    href="http://localhost:8000/docs"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline underline-offset-4 hover:text-primary/80"
                  >
                    localhost:8000/docs
                  </a>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <PropertyDetail
        property={selectedProperty}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />
    </div>
  );
}
