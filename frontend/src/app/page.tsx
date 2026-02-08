'use client';

import { useState, useEffect } from 'react';
import {
  Building2,
  TrendingUp,
  TrendingDown,
  Calculator,
  Bell,
  BarChart3,
  Search,
  Minus,
  Landmark,
  Briefcase,
  ChevronRight,
  DollarSign,
  Home as HomeIcon,
  Percent,
  Activity,
} from 'lucide-react';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { LoadingCard } from '@/components/LoadingCard';
import { useTopOpportunities } from '@/hooks/useProperties';
import { MetricsBar, PriceCapScatter, PriceDistribution } from '@/components/charts';
import { formatPrice, getScoreColor } from '@/lib/formatters';
import { marketApi } from '@/lib/api';
import type { MarketSummaryResponse } from '@/lib/types';
import { useTranslation } from '@/i18n/LanguageContext';

export default function Home() {
  const { t, locale } = useTranslation();
  const [region, setRegion] = useState('montreal');
  const [marketData, setMarketData] = useState<MarketSummaryResponse | null>(null);
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

  const features = [
    {
      title: t('home.featureSearch'),
      description: t('home.featureSearchDesc'),
      icon: Search,
      href: '/search',
      gradient: 'from-blue-500/15 to-blue-600/5 dark:from-blue-500/20 dark:to-blue-600/5',
      iconBg: 'bg-blue-500/10 dark:bg-blue-500/20',
      iconColor: 'text-blue-600 dark:text-blue-400',
    },
    {
      title: t('home.featureCompare'),
      description: t('home.featureCompareDesc'),
      icon: BarChart3,
      href: '/compare',
      gradient: 'from-emerald-500/15 to-emerald-600/5 dark:from-emerald-500/20 dark:to-emerald-600/5',
      iconBg: 'bg-emerald-500/10 dark:bg-emerald-500/20',
      iconColor: 'text-emerald-600 dark:text-emerald-400',
    },
    {
      title: t('home.featureCalc'),
      description: t('home.featureCalcDesc'),
      icon: Calculator,
      href: '/calculator',
      gradient: 'from-violet-500/15 to-violet-600/5 dark:from-violet-500/20 dark:to-violet-600/5',
      iconBg: 'bg-violet-500/10 dark:bg-violet-500/20',
      iconColor: 'text-violet-600 dark:text-violet-400',
    },
    {
      title: t('home.featureAlerts'),
      description: t('home.featureAlertsDesc'),
      icon: Bell,
      href: '/alerts',
      gradient: 'from-amber-500/15 to-amber-600/5 dark:from-amber-500/20 dark:to-amber-600/5',
      iconBg: 'bg-amber-500/10 dark:bg-amber-500/20',
      iconColor: 'text-amber-600 dark:text-amber-400',
    },
    {
      title: t('home.featurePortfolio'),
      description: t('home.featurePortfolioDesc'),
      icon: Briefcase,
      href: '/portfolio',
      gradient: 'from-rose-500/15 to-rose-600/5 dark:from-rose-500/20 dark:to-rose-600/5',
      iconBg: 'bg-rose-500/10 dark:bg-rose-500/20',
      iconColor: 'text-rose-600 dark:text-rose-400',
    },
  ];

  useEffect(() => {
    marketApi.summary().then(setMarketData).catch(() => {});
  }, []);

  const properties = topOpportunities?.results || [];
  const hasData = properties.length > 0;

  return (
    <div className="space-y-10">
      {/* Hero Section */}
      <section className="relative -mx-4 sm:-mx-6 lg:-mx-8 -mt-6 px-4 sm:px-6 lg:px-8 pt-12 pb-14 overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-background to-violet-50/50 dark:from-blue-950/40 dark:via-background dark:to-violet-950/30" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-100/40 via-transparent to-transparent dark:from-blue-900/20" />

        <div className="relative max-w-3xl mx-auto text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border bg-background/80 backdrop-blur-sm text-sm text-muted-foreground">
            <Activity className="h-3.5 w-3.5 text-emerald-500" />
            {t('home.heroTag')}
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">
            {t('home.title')}
          </h1>

          <p className="text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            {t('home.subtitle')}
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
            <Button size="lg" asChild className="shadow-md">
              <Link href="/search">
                <Search className="mr-2 h-4 w-4" />
                {t('home.searchProperties')}
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild className="bg-background/80 backdrop-blur-sm">
              <Link href="/calculator">
                <Calculator className="mr-2 h-4 w-4" />
                {t('home.quickCalculator')}
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Interest Rates Ticker */}
      {marketData && (marketData.mortgage_rate != null || marketData.policy_rate != null) && (
        <section className="-mt-4">
          <Card className="border-dashed">
            <CardContent className="py-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <Landmark className="h-4 w-4" />
                  {t('home.currentRates')}
                </div>
                <div className="flex flex-wrap items-center gap-6">
                  {marketData.mortgage_rate != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{t('home.mortgageRate')}</span>
                      <span className="text-sm font-bold tabular-nums">{marketData.mortgage_rate.toFixed(2)}%</span>
                      {marketData.mortgage_direction === 'down' ? (
                        <TrendingDown className="h-3.5 w-3.5 text-emerald-500" />
                      ) : marketData.mortgage_direction === 'up' ? (
                        <TrendingUp className="h-3.5 w-3.5 text-red-500" />
                      ) : (
                        <Minus className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </div>
                  )}
                  {marketData.policy_rate != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{t('home.policyRate')}</span>
                      <span className="text-sm font-bold tabular-nums">{marketData.policy_rate.toFixed(2)}%</span>
                      {marketData.policy_direction === 'down' ? (
                        <TrendingDown className="h-3.5 w-3.5 text-emerald-500" />
                      ) : marketData.policy_direction === 'up' ? (
                        <TrendingUp className="h-3.5 w-3.5 text-red-500" />
                      ) : (
                        <Minus className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </div>
                  )}
                  {marketData.prime_rate != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{t('home.primeRate')}</span>
                      <span className="text-sm font-bold tabular-nums">{marketData.prime_rate.toFixed(2)}%</span>
                    </div>
                  )}
                  {marketData.cpi != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{t('home.cpiIndex')}</span>
                      <span className="text-sm font-bold tabular-nums">{marketData.cpi.toFixed(1)}</span>
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-muted-foreground/60">{t('home.bankOfCanada')}</span>
              </div>
            </CardContent>
          </Card>
        </section>
      )}

      {/* Feature Cards */}
      <section>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {features.map((feature) => (
            <Link key={feature.href} href={feature.href} className="group">
              <Card className={`h-full border-0 bg-gradient-to-br ${feature.gradient} transition-all duration-200 group-hover:shadow-md group-hover:scale-[1.02]`}>
                <CardContent className="pt-5 pb-4 px-4">
                  <div className={`inline-flex p-2 rounded-lg ${feature.iconBg} mb-3`}>
                    <feature.icon className={`h-5 w-5 ${feature.iconColor}`} />
                  </div>
                  <h3 className="font-semibold text-sm">{feature.title}</h3>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{feature.description}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* Market Overview Section Header */}
      <section className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold tracking-tight">{t('home.marketOverview')}</h2>
            <p className="text-sm text-muted-foreground">{t('home.marketOverviewDesc')}</p>
          </div>
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

        {/* Analytics Content */}
        {isLoading ? (
          <LoadingCard message={t('home.loadingMarket')} description={t('home.loadingMarketDesc')} />
        ) : hasData ? (
          <div className="space-y-6">
            {/* KPI Stats Row */}
            <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
              <Card className="relative overflow-hidden">
                <div className="absolute top-0 right-0 p-3 opacity-[0.07]">
                  <Building2 className="h-12 w-12" />
                </div>
                <CardHeader className="pb-1 pt-4 px-4">
                  <CardDescription className="text-xs">{t('home.propertiesAnalyzed')}</CardDescription>
                </CardHeader>
                <CardContent className="pb-4 px-4">
                  <div className="text-3xl font-bold tabular-nums">{properties.length}</div>
                  <p className="text-xs text-muted-foreground mt-0.5">{t('home.inRegion')}</p>
                </CardContent>
              </Card>

              <Card className="relative overflow-hidden">
                <div className="absolute top-0 right-0 p-3 opacity-[0.07]">
                  <Activity className="h-12 w-12" />
                </div>
                <CardHeader className="pb-1 pt-4 px-4">
                  <CardDescription className="text-xs">{t('home.avgScore')}</CardDescription>
                </CardHeader>
                <CardContent className="pb-4 px-4">
                  <div className="text-3xl font-bold tabular-nums">
                    {Math.round(
                      properties.reduce((sum, p) => sum + p.metrics.score, 0) / properties.length
                    )}
                    <span className="text-lg text-muted-foreground font-normal">/100</span>
                  </div>
                </CardContent>
              </Card>

              <Card className="relative overflow-hidden">
                <div className="absolute top-0 right-0 p-3 opacity-[0.07]">
                  <Percent className="h-12 w-12" />
                </div>
                <CardHeader className="pb-1 pt-4 px-4">
                  <CardDescription className="text-xs">{t('home.avgCapRate')}</CardDescription>
                </CardHeader>
                <CardContent className="pb-4 px-4">
                  <div className="text-3xl font-bold tabular-nums">
                    {(
                      properties
                        .filter((p) => p.metrics.cap_rate != null)
                        .reduce((sum, p) => sum + (p.metrics.cap_rate || 0), 0) /
                      (properties.filter((p) => p.metrics.cap_rate != null).length || 1)
                    ).toFixed(1)}
                    <span className="text-lg text-muted-foreground font-normal">%</span>
                  </div>
                </CardContent>
              </Card>

              <Card className="relative overflow-hidden">
                <div className="absolute top-0 right-0 p-3 opacity-[0.07]">
                  <DollarSign className="h-12 w-12" />
                </div>
                <CardHeader className="pb-1 pt-4 px-4">
                  <CardDescription className="text-xs">{t('home.positiveCashFlow')}</CardDescription>
                </CardHeader>
                <CardContent className="pb-4 px-4">
                  <div className="text-3xl font-bold tabular-nums">
                    {properties.filter((p) => p.metrics.is_positive_cash_flow).length}
                    <span className="text-lg text-muted-foreground font-normal">/{properties.length}</span>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Charts Grid */}
            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-muted-foreground" />
                    {t('home.topByScore')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <MetricsBar properties={properties} metric="score" />
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{t('home.priceVsCap')}</CardTitle>
                  <CardDescription className="text-xs">
                    {t('home.bubbleSize')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <PriceCapScatter properties={properties} />
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{t('home.priceDistribution')}</CardTitle>
                  <CardDescription className="text-xs">{t('home.priceDistributionDesc')}</CardDescription>
                </CardHeader>
                <CardContent>
                  <PriceDistribution properties={properties} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{t('home.capRateComparison')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <MetricsBar properties={properties} metric="cap_rate" />
                </CardContent>
              </Card>
            </div>

            {/* Top Opportunities */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    {t('home.topOpportunities')}
                  </CardTitle>
                  <Button variant="ghost" size="sm" asChild className="text-xs gap-1">
                    <Link href="/search">
                      {t('common.viewAll')}
                      <ChevronRight className="h-3 w-3" />
                    </Link>
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {properties.slice(0, 5).map((property, index) => (
                    <div key={property.listing.id}>
                      <div className="flex items-center justify-between py-3 px-2 rounded-lg hover:bg-muted/50 transition-colors">
                        <div className="flex items-center gap-4">
                          <div className="flex items-center gap-3">
                            <span className="text-xs text-muted-foreground/60 font-mono w-4 text-right">
                              {index + 1}
                            </span>
                            <div
                              className={`w-9 h-9 rounded-lg flex items-center justify-center text-white text-sm font-bold ${getScoreColor(
                                property.metrics.score
                              )}`}
                            >
                              {property.metrics.score}
                            </div>
                          </div>
                          <div className="min-w-0">
                            <p className="font-medium text-sm truncate">{property.listing.address}</p>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 font-normal">
                                {property.listing.property_type}
                              </Badge>
                              <span>{t('home.units', { count: property.listing.units })}</span>
                              <span className="text-muted-foreground/40">·</span>
                              <span className="font-medium text-foreground/80">{formatPrice(property.listing.price, locale)}</span>
                            </div>
                          </div>
                        </div>
                        <div className="text-right shrink-0 ml-4">
                          <p className="text-sm font-medium tabular-nums">
                            {t('home.cap', { rate: property.metrics.cap_rate?.toFixed(1) ?? '-' })}
                          </p>
                          <p
                            className={`text-xs tabular-nums ${
                              property.metrics.is_positive_cash_flow
                                ? 'text-emerald-600 dark:text-emerald-400'
                                : 'text-red-600 dark:text-red-400'
                            }`}
                          >
                            {property.metrics.cash_flow_monthly != null
                              ? `${formatPrice(property.metrics.cash_flow_monthly, locale)}${t('common.perMonth')}`
                              : '-'}
                          </p>
                        </div>
                      </div>
                      {index < 4 && <Separator />}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
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
      </section>
    </div>
  );
}
