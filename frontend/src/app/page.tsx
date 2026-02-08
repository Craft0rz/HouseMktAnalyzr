'use client';

import { useState, useEffect } from 'react';
import { Building2, TrendingUp, TrendingDown, Calculator, Bell, BarChart3, Search, Minus, Landmark } from 'lucide-react';
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
    { title: t('home.featureSearch'), description: t('home.featureSearchDesc'), icon: Search, href: '/search', color: 'text-blue-500' },
    { title: t('home.featureCompare'), description: t('home.featureCompareDesc'), icon: BarChart3, href: '/compare', color: 'text-green-500' },
    { title: t('home.featureCalc'), description: t('home.featureCalcDesc'), icon: Calculator, href: '/calculator', color: 'text-purple-500' },
    { title: t('home.featureAlerts'), description: t('home.featureAlertsDesc'), icon: Bell, href: '/alerts', color: 'text-orange-500' },
  ];

  useEffect(() => {
    marketApi.summary().then(setMarketData).catch(() => {});
  }, []);

  const properties = topOpportunities?.results || [];
  const hasData = properties.length > 0;

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">
          {t('home.title')}
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          {t('home.subtitle')}
        </p>
        <div className="flex gap-4 justify-center pt-4">
          <Button size="lg" asChild>
            <Link href="/search">
              <Building2 className="mr-2 h-5 w-5" />
              {t('home.searchProperties')}
            </Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="/calculator">
              <Calculator className="mr-2 h-5 w-5" />
              {t('home.quickCalculator')}
            </Link>
          </Button>
        </div>
      </div>

      {/* Quick Links */}
      <div className="grid gap-4 md:grid-cols-4">
        {features.map((feature) => (
          <Link key={feature.href} href={feature.href}>
            <Card className="h-full transition-colors hover:bg-muted/50">
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <feature.icon className={`h-8 w-8 ${feature.color}`} />
                  <div>
                    <h3 className="font-semibold">{feature.title}</h3>
                    <p className="text-sm text-muted-foreground">{feature.description}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Region Selector */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-tight">{t('home.marketOverview')}</h2>
        <Select value={region} onValueChange={setRegion}>
          <SelectTrigger className="w-[200px]">
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

      {/* Market Rates Banner */}
      {marketData && (marketData.mortgage_rate != null || marketData.policy_rate != null) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Landmark className="h-4 w-4" />
              {t('home.currentRates')}
              <span className="text-xs text-muted-foreground font-normal ml-auto">{t('home.bankOfCanada')}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {marketData.mortgage_rate != null && (
                <div className="flex items-center gap-3">
                  <div>
                    <div className="text-xs text-muted-foreground">{t('home.mortgageRate')}</div>
                    <div className="text-2xl font-bold">{marketData.mortgage_rate.toFixed(2)}%</div>
                  </div>
                  {marketData.mortgage_direction === 'down' ? (
                    <TrendingDown className="h-5 w-5 text-green-500" />
                  ) : marketData.mortgage_direction === 'up' ? (
                    <TrendingUp className="h-5 w-5 text-red-500" />
                  ) : (
                    <Minus className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              )}
              {marketData.policy_rate != null && (
                <div className="flex items-center gap-3">
                  <div>
                    <div className="text-xs text-muted-foreground">{t('home.policyRate')}</div>
                    <div className="text-2xl font-bold">{marketData.policy_rate.toFixed(2)}%</div>
                  </div>
                  {marketData.policy_direction === 'down' ? (
                    <TrendingDown className="h-5 w-5 text-green-500" />
                  ) : marketData.policy_direction === 'up' ? (
                    <TrendingUp className="h-5 w-5 text-red-500" />
                  ) : (
                    <Minus className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              )}
              {marketData.prime_rate != null && (
                <div>
                  <div className="text-xs text-muted-foreground">{t('home.primeRate')}</div>
                  <div className="text-2xl font-bold">{marketData.prime_rate.toFixed(2)}%</div>
                </div>
              )}
              {marketData.cpi != null && (
                <div>
                  <div className="text-xs text-muted-foreground">{t('home.cpiIndex')}</div>
                  <div className="text-2xl font-bold">{marketData.cpi.toFixed(1)}</div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Analytics Section */}
      {isLoading ? (
        <LoadingCard message={t('home.loadingMarket')} description={t('home.loadingMarketDesc')} />
      ) : hasData ? (
        <>
          {/* Market Overview */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>{t('home.propertiesAnalyzed')}</CardDescription>
                <CardTitle className="text-3xl">{properties.length}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>{t('home.avgScore')}</CardDescription>
                <CardTitle className="text-3xl">
                  {Math.round(
                    properties.reduce((sum, p) => sum + p.metrics.score, 0) / properties.length
                  )}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>{t('home.avgCapRate')}</CardDescription>
                <CardTitle className="text-3xl">
                  {(
                    properties
                      .filter((p) => p.metrics.cap_rate != null)
                      .reduce((sum, p) => sum + (p.metrics.cap_rate || 0), 0) /
                    properties.filter((p) => p.metrics.cap_rate != null).length
                  ).toFixed(1)}
                  %
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>{t('home.positiveCashFlow')}</CardDescription>
                <CardTitle className="text-3xl">
                  {properties.filter((p) => p.metrics.is_positive_cash_flow).length}/
                  {properties.length}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          {/* Charts Row */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  {t('home.topByScore')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <MetricsBar properties={properties} metric="score" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('home.priceVsCap')}</CardTitle>
                <CardDescription>
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
              <CardHeader>
                <CardTitle>{t('home.priceDistribution')}</CardTitle>
                <CardDescription>{t('home.priceDistributionDesc')}</CardDescription>
              </CardHeader>
              <CardContent>
                <PriceDistribution properties={properties} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('home.capRateComparison')}</CardTitle>
              </CardHeader>
              <CardContent>
                <MetricsBar properties={properties} metric="cap_rate" />
              </CardContent>
            </Card>
          </div>

          {/* Top Opportunities Table */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Building2 className="h-5 w-5" />
                  {t('home.topOpportunities')}
                </span>
                <Button variant="outline" size="sm" asChild>
                  <Link href="/search">{t('common.viewAll')}</Link>
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {properties.slice(0, 5).map((property, index) => (
                  <div key={property.listing.id}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div
                          className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold ${getScoreColor(
                            property.metrics.score
                          )}`}
                        >
                          {property.metrics.score}
                        </div>
                        <div>
                          <p className="font-medium">{property.listing.address}</p>
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Badge variant="outline">{property.listing.property_type}</Badge>
                            <span>{t('home.units', { count: property.listing.units })}</span>
                            <span>•</span>
                            <span>{formatPrice(property.listing.price, locale)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-medium">
                          {t('home.cap', { rate: property.metrics.cap_rate?.toFixed(1) ?? '-' })}
                        </p>
                        <p
                          className={`text-sm ${
                            property.metrics.is_positive_cash_flow
                              ? 'text-green-600'
                              : 'text-red-600'
                          }`}
                        >
                          {property.metrics.cash_flow_monthly != null
                            ? `${formatPrice(property.metrics.cash_flow_monthly, locale)}${t('common.perMonth')}`
                            : '-'}
                        </p>
                      </div>
                    </div>
                    {index < 4 && <Separator className="mt-4" />}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>{t('home.gettingStarted')}</CardTitle>
            <CardDescription>
              {t('home.gettingStartedDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm text-muted-foreground">{t('home.startBackend')}</p>
            <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
              <code>
                cd HouseMktAnalyzr{'\n'}
                set PYTHONPATH=src{'\n'}
                python -m uvicorn backend.app.main:app --reload
              </code>
            </pre>
            <p className="text-sm text-muted-foreground mt-4">
              {t('home.apiDocs')}{' '}
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline"
              >
                http://localhost:8000/docs
              </a>
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
