'use client';

import { useEffect, useState } from 'react';
import { ExternalLink, MapPin, Home, DollarSign, TrendingUp, TrendingDown, Calculator, Landmark, PiggyBank, ArrowUpRight, ArrowDownRight, Plus, Wrench, Loader2, Footprints, Bus, Bike, Sparkles, AlertTriangle, BarChart3, Minus, Users, Shield, Hammer } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { ScoreBreakdown } from '@/components/charts';
import { useComparison } from '@/lib/comparison-context';
import { propertiesApi, marketApi } from '@/lib/api';
import type { PropertyWithMetrics, PropertyListing, MarketSummaryResponse, RentTrendResponse, DemographicProfile, NeighbourhoodResponse } from '@/lib/types';

interface PropertyDetailProps {
  property: PropertyWithMetrics | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const formatPrice = (price: number) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(price);
};

const formatPercent = (value: number | null | undefined) => {
  if (value == null) return '-';
  return `${value.toFixed(2)}%`;
};

const getScoreColor = (score: number) => {
  if (score >= 70) return 'text-green-600';
  if (score >= 50) return 'text-yellow-600';
  return 'text-red-600';
};

const getScoreBg = (score: number) => {
  if (score >= 70) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
};

const getWalkLabel = (score: number) => {
  if (score >= 90) return "Walker's Paradise";
  if (score >= 70) return 'Very Walkable';
  if (score >= 50) return 'Somewhat Walkable';
  if (score >= 25) return 'Car-Dependent';
  return 'Almost All Errands Require a Car';
};

const getConditionColor = (score: number) => {
  if (score >= 7) return 'text-green-600';
  if (score >= 5) return 'text-yellow-600';
  return 'text-red-600';
};

const getConditionBg = (score: number) => {
  if (score >= 7) return 'bg-green-500';
  if (score >= 5) return 'bg-yellow-500';
  return 'bg-red-500';
};

const getConditionLabel = (score: number) => {
  if (score >= 8) return 'Excellent';
  if (score >= 6) return 'Good';
  if (score >= 4) return 'Fair';
  return 'Poor';
};

const conditionCategoryIcons: Record<string, string> = {
  kitchen: '🍳',
  bathroom: '🚿',
  floors: '🏠',
  exterior: '🏢',
};

const getPropertyTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    DUPLEX: 'Duplex',
    TRIPLEX: 'Triplex',
    QUADPLEX: 'Quadplex',
    MULTIPLEX: '5+ Units',
    HOUSE: 'House',
  };
  return labels[type] || type;
};

// Circular score gauge component (0-100)
function ScoreGauge({ score, size = 120 }: { score: number; size?: number }) {
  const radius = (size - 12) / 2;
  const circumference = radius * 2 * Math.PI;
  const progress = Math.min(score / 100, 1) * circumference;
  const strokeWidth = 8;

  const getColor = (s: number) => {
    if (s >= 70) return '#22c55e'; // green-500
    if (s >= 50) return '#eab308'; // yellow-500
    return '#ef4444'; // red-500
  };

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="none"
          className="text-muted/20"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={getColor(score)}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold" style={{ color: getColor(score) }}>
          {score.toFixed(0)}
        </span>
        <span className="text-xs text-muted-foreground">/ 100</span>
      </div>
    </div>
  );
}

// Metric bar with comparison
function MetricBar({
  label,
  value,
  benchmark,
  unit = '',
  higherIsBetter = true,
}: {
  label: string;
  value: number | null | undefined;
  benchmark: number;
  unit?: string;
  higherIsBetter?: boolean;
}) {
  if (value == null) return null;

  const percentage = Math.min((value / (benchmark * 1.5)) * 100, 100);
  const isGood = higherIsBetter ? value >= benchmark : value <= benchmark;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className={`font-medium ${isGood ? 'text-green-600' : 'text-amber-600'}`}>
          {value.toFixed(1)}{unit}
        </span>
      </div>
      <div className="relative">
        <Progress value={percentage} className="h-2" />
        {/* Benchmark indicator */}
        <div
          className="absolute top-0 w-0.5 h-2 bg-foreground/50"
          style={{ left: `${(benchmark / (benchmark * 1.5)) * 100}%` }}
          title={`Benchmark: ${benchmark}${unit}`}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>0{unit}</span>
        <span className="text-xs">Target: {benchmark}{unit}</span>
      </div>
    </div>
  );
}

export function PropertyDetail({ property, open, onOpenChange }: PropertyDetailProps) {
  const { addProperty, selectedProperties } = useComparison();
  const [enrichedListing, setEnrichedListing] = useState<PropertyListing | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [marketData, setMarketData] = useState<MarketSummaryResponse | null>(null);
  const [rentTrend, setRentTrend] = useState<RentTrendResponse | null>(null);
  const [demographics, setDemographics] = useState<DemographicProfile | null>(null);
  const [neighbourhood, setNeighbourhood] = useState<NeighbourhoodResponse | null>(null);

  // Fetch enriched detail data (walk score, condition score) when sheet opens
  useEffect(() => {
    if (!open || !property) {
      setEnrichedListing(null);
      setDetailError(null);
      setRentTrend(null);
      setDemographics(null);
      setNeighbourhood(null);
      return;
    }

    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);

    propertiesApi.getDetails(property.listing.id).then((detail) => {
      if (!cancelled) {
        setEnrichedListing(detail);
      }
    }).catch((err) => {
      if (!cancelled) {
        setDetailError(err instanceof Error ? err.message : 'Failed to load details');
      }
    }).finally(() => {
      if (!cancelled) setDetailLoading(false);
    });

    // Fetch market data in parallel
    marketApi.summary().then((data) => {
      if (!cancelled) setMarketData(data);
    }).catch(() => {});

    // Fetch neighbourhood safety/development data
    const boroughName = property.listing.city || 'Montreal';
    const assessmentVal = property.listing.municipal_assessment || undefined;
    marketApi.neighbourhood(boroughName, assessmentVal).then((data) => {
      if (!cancelled) setNeighbourhood(data);
    }).catch(() => {});

    // Fetch demographics for this property's city
    const cityName = property.listing.city || 'Montreal';
    const estRent = property.listing.estimated_rent || undefined;
    marketApi.demographics(cityName, estRent ? Math.round(estRent / (property.listing.units || 1)) : undefined).then((data) => {
      if (!cancelled) setDemographics(data);
    }).catch(() => {});

    // Fetch rent trend for this property's city/zone
    const bedrooms = Math.min(property.listing.bedrooms || 2, 3);
    const zone = property.listing.city || 'Montreal CMA Total';
    marketApi.rentTrend(zone, bedrooms).then((data) => {
      if (!cancelled) setRentTrend(data);
    }).catch(() => {
      // Try CMA-level fallback
      if (zone !== 'Montreal CMA Total') {
        marketApi.rentTrend('Montreal CMA Total', bedrooms).then((data) => {
          if (!cancelled) setRentTrend(data);
        }).catch(() => {});
      }
    });

    return () => { cancelled = true; };
  }, [open, property?.listing.id]);

  if (!property) return null;

  const { metrics } = property;
  // Use enriched listing if available, otherwise fall back to search data
  const listing = enrichedListing || property.listing;

  // Calculate mortgage estimates (20% down, 5% rate, 25 years)
  const downPaymentPct = 0.20;
  const interestRate = 0.05;
  const amortizationYears = 25;
  const downPayment = listing.price * downPaymentPct;
  const principal = listing.price - downPayment;
  const monthlyRate = interestRate / 12;
  const numPayments = amortizationYears * 12;
  const monthlyMortgage = principal * (monthlyRate * Math.pow(1 + monthlyRate, numPayments)) / (Math.pow(1 + monthlyRate, numPayments) - 1);

  // Cash flow breakdown
  const monthlyIncome = metrics.estimated_monthly_rent;
  const monthlyExpenses = {
    mortgage: monthlyMortgage,
    taxes: (listing.annual_taxes || listing.price * 0.012) / 12, // ~1.2% of price if unknown
    insurance: listing.price * 0.004 / 12, // ~0.4% of price
    maintenance: monthlyIncome * 0.05, // 5% of rent
    vacancy: monthlyIncome * 0.05, // 5% vacancy allowance
  };
  const totalExpenses = Object.values(monthlyExpenses).reduce((a, b) => a + b, 0);
  const netCashFlow = monthlyIncome - totalExpenses;

  const isInComparison = selectedProperties.some(p => p.listing.id === listing.id);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        <SheetHeader className="px-6 pt-6">
          <SheetTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            {listing.address}
          </SheetTitle>
          <SheetDescription>
            {listing.city}
            {listing.postal_code && ` • ${listing.postal_code}`}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 px-6 pb-8 space-y-5">
          {/* Score and Price Hero */}
          <div className="p-4 rounded-lg bg-muted/50 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <ScoreGauge score={metrics.score} size={100} />
                <div>
                  <div className="text-sm text-muted-foreground">Investment Score</div>
                  <div className="text-sm mt-1">
                    {metrics.score >= 70 ? (
                      <Badge className="bg-green-500">Excellent</Badge>
                    ) : metrics.score >= 50 ? (
                      <Badge className="bg-yellow-500">Good</Badge>
                    ) : (
                      <Badge variant="destructive">Below Average</Badge>
                    )}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-muted-foreground">Asking Price</div>
                <div className="text-2xl font-bold">{formatPrice(listing.price)}</div>
                <div className="text-xs text-muted-foreground">
                  {formatPrice(metrics.price_per_unit)}/unit
                </div>
              </div>
            </div>
            {/* Two-pillar summary */}
            {metrics.score_breakdown && Object.keys(metrics.score_breakdown).length > 0 && (() => {
              const fin = (metrics.score_breakdown.cap_rate ?? 0) + (metrics.score_breakdown.cash_flow ?? 0) + (metrics.score_breakdown.price_per_unit ?? 0);
              const loc = (metrics.score_breakdown.neighbourhood_safety ?? 0) + (metrics.score_breakdown.neighbourhood_vacancy ?? 0) + (metrics.score_breakdown.neighbourhood_rent_growth ?? 0) + (metrics.score_breakdown.neighbourhood_affordability ?? 0) + (metrics.score_breakdown.condition ?? 0);
              const hasLoc = loc > 0;
              return (
                <div className="flex gap-3">
                  <div className="flex-1 rounded-md bg-background/60 px-3 py-2">
                    <div className="text-xs text-muted-foreground">Financial</div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-lg font-semibold tabular-nums">{fin.toFixed(0)}</span>
                      <span className="text-xs text-muted-foreground">/70</span>
                    </div>
                    <div className="mt-1 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                      <div className="h-full rounded-full bg-green-500 transition-all" style={{ width: `${Math.min(100, (fin / 70) * 100)}%` }} />
                    </div>
                  </div>
                  <div className="flex-1 rounded-md bg-background/60 px-3 py-2">
                    <div className="text-xs text-muted-foreground">Location & Quality</div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-lg font-semibold tabular-nums">{hasLoc ? loc.toFixed(0) : '--'}</span>
                      <span className="text-xs text-muted-foreground">/30</span>
                    </div>
                    <div className="mt-1 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                      <div className="h-full rounded-full bg-blue-500 transition-all" style={{ width: `${hasLoc ? Math.min(100, (loc / 30) * 100) : 0}%` }} />
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Quick Actions */}
          <div className="flex gap-2">
            <Button asChild variant="outline" className="flex-1">
              <a href={listing.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                View on Centris
              </a>
            </Button>
            <Button
              variant={isInComparison ? 'secondary' : 'default'}
              onClick={() => !isInComparison && addProperty(property)}
              disabled={isInComparison || selectedProperties.length >= 4}
            >
              <Plus className="mr-2 h-4 w-4" />
              {isInComparison ? 'In Compare' : 'Compare'}
            </Button>
          </div>

          <Separator />

          {/* Score Breakdown */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Calculator className="h-4 w-4" />
                Score Breakdown
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScoreBreakdown scoreBreakdown={metrics.score_breakdown} />
            </CardContent>
          </Card>

          {/* Monthly Cash Flow Breakdown */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <PiggyBank className="h-4 w-4" />
                Monthly Cash Flow
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Income */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium flex items-center gap-2">
                    <ArrowUpRight className="h-4 w-4 text-green-500" />
                    Rental Income
                    {metrics.rent_source === 'cmhc_estimate' && (
                      <span className="text-[10px] font-normal text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                        Est. (CMHC avg)
                      </span>
                    )}
                  </span>
                  <span className="font-bold text-green-600">
                    +{formatPrice(monthlyIncome)}
                  </span>
                </div>
              </div>

              <Separator />

              {/* Expenses */}
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground flex items-center gap-2">
                    <ArrowDownRight className="h-4 w-4 text-red-500" />
                    Expenses
                  </span>
                </div>
                <div className="pl-6 space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Mortgage</span>
                    <span className="text-red-600">-{formatPrice(monthlyExpenses.mortgage)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Property Taxes</span>
                    <span className="text-red-600">-{formatPrice(monthlyExpenses.taxes)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Insurance</span>
                    <span className="text-red-600">-{formatPrice(monthlyExpenses.insurance)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Maintenance (5%)</span>
                    <span className="text-red-600">-{formatPrice(monthlyExpenses.maintenance)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Vacancy (5%)</span>
                    <span className="text-red-600">-{formatPrice(monthlyExpenses.vacancy)}</span>
                  </div>
                </div>
                <div className="flex justify-between pt-2 border-t">
                  <span className="text-sm font-medium">Total Expenses</span>
                  <span className="font-bold text-red-600">-{formatPrice(totalExpenses)}</span>
                </div>
              </div>

              <Separator />

              {/* Net Cash Flow */}
              <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
                <span className="font-semibold">Net Monthly Cash Flow</span>
                <span className={`text-xl font-bold ${netCashFlow >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {netCashFlow >= 0 ? '+' : ''}{formatPrice(netCashFlow)}
                </span>
              </div>

              <div className="text-xs text-muted-foreground text-center">
                Annual: {formatPrice(netCashFlow * 12)} |
                {' '}ROI: {((netCashFlow * 12) / downPayment * 100).toFixed(1)}% on down payment
              </div>
            </CardContent>
          </Card>

          {/* Mortgage Details */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Landmark className="h-4 w-4" />
                Mortgage Estimate
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground">Down Payment (20%)</div>
                  <div className="font-medium">{formatPrice(downPayment)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Loan Amount</div>
                  <div className="font-medium">{formatPrice(principal)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Monthly Payment</div>
                  <div className="font-medium">{formatPrice(monthlyMortgage)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Interest Rate</div>
                  <div className="font-medium">{(interestRate * 100).toFixed(1)}%</div>
                </div>
              </div>
              <div className="text-xs text-muted-foreground">
                Based on {amortizationYears}-year amortization. Actual terms may vary.
              </div>
            </CardContent>
          </Card>

          {/* Key Investment Metrics */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                Key Metrics
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <MetricBar
                label="Cap Rate"
                value={metrics.cap_rate}
                benchmark={5}
                unit="%"
                higherIsBetter={true}
              />
              <MetricBar
                label="Gross Yield"
                value={metrics.gross_rental_yield}
                benchmark={7}
                unit="%"
                higherIsBetter={true}
              />
              <div className="grid grid-cols-2 gap-4 pt-2 text-sm">
                <div className="p-3 rounded-lg bg-muted/50">
                  <div className="text-muted-foreground">Price/sqft</div>
                  <div className="font-bold">
                    {metrics.price_per_sqft ? `$${metrics.price_per_sqft.toFixed(0)}` : 'N/A'}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <div className="text-muted-foreground">Assessment</div>
                  <div className="font-bold">
                    {listing.municipal_assessment ? formatPrice(listing.municipal_assessment) : 'N/A'}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Walk Score / Condition — loading state */}
          {detailLoading && (
            <Card>
              <CardContent className="py-6">
                <div className="flex items-center gap-3 justify-center text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Loading walkability & condition data...</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error state */}
          {detailError && (
            <Card className="border-destructive/50">
              <CardContent className="py-4">
                <p className="text-sm text-destructive text-center">{detailError}</p>
              </CardContent>
            </Card>
          )}

          {/* Walk Score */}
          {!detailLoading && (listing.walk_score != null || listing.transit_score != null || listing.bike_score != null) && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Footprints className="h-4 w-4" />
                  Walkability
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {listing.walk_score != null && (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm">
                        <Footprints className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>Walk Score</span>
                      </div>
                      <span className={`text-sm font-bold ${getScoreColor(listing.walk_score)}`}>{listing.walk_score}</span>
                    </div>
                    <div className="relative h-2 rounded-full bg-muted overflow-hidden">
                      <div className={`absolute inset-y-0 left-0 rounded-full transition-all ${getScoreBg(listing.walk_score)}`} style={{ width: `${listing.walk_score}%` }} />
                    </div>
                    <p className="text-xs text-muted-foreground">{getWalkLabel(listing.walk_score)}</p>
                  </div>
                )}
                {listing.transit_score != null && (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm">
                        <Bus className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>Transit Score</span>
                      </div>
                      <span className={`text-sm font-bold ${getScoreColor(listing.transit_score)}`}>{listing.transit_score}</span>
                    </div>
                    <div className="relative h-2 rounded-full bg-muted overflow-hidden">
                      <div className={`absolute inset-y-0 left-0 rounded-full transition-all ${getScoreBg(listing.transit_score)}`} style={{ width: `${listing.transit_score}%` }} />
                    </div>
                  </div>
                )}
                {listing.bike_score != null && (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm">
                        <Bike className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>Bike Score</span>
                      </div>
                      <span className={`text-sm font-bold ${getScoreColor(listing.bike_score)}`}>{listing.bike_score}</span>
                    </div>
                    <div className="relative h-2 rounded-full bg-muted overflow-hidden">
                      <div className={`absolute inset-y-0 left-0 rounded-full transition-all ${getScoreBg(listing.bike_score)}`} style={{ width: `${listing.bike_score}%` }} />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* AI Condition Score */}
          {!detailLoading && listing.condition_score != null && listing.condition_details && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  Property Condition
                  <Badge variant="outline" className="text-[10px] ml-auto font-normal gap-1">
                    <Sparkles className="h-3 w-3" />
                    AI Analysis
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Overall score hero */}
                <div className="flex items-center gap-4 p-3 rounded-lg bg-muted/50">
                  <div className={`flex items-center justify-center w-14 h-14 rounded-full border-[3px] ${
                    listing.condition_score >= 7 ? 'border-green-500' :
                    listing.condition_score >= 5 ? 'border-yellow-500' : 'border-red-500'
                  }`}>
                    <span className={`text-xl font-bold ${getConditionColor(listing.condition_score)}`}>
                      {listing.condition_score.toFixed(1)}
                    </span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-semibold ${getConditionColor(listing.condition_score)}`}>
                        {getConditionLabel(listing.condition_score)}
                      </span>
                      {listing.condition_details.renovation_needed && (
                        <Badge variant="destructive" className="text-[10px] gap-1 h-5">
                          <AlertTriangle className="h-3 w-3" />
                          Reno Needed
                        </Badge>
                      )}
                    </div>
                    <div className="relative h-2 rounded-full bg-muted overflow-hidden mt-2">
                      <div
                        className={`absolute inset-y-0 left-0 rounded-full transition-all ${getConditionBg(listing.condition_score)}`}
                        style={{ width: `${listing.condition_score * 10}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                      <span>Poor</span>
                      <span>Excellent</span>
                    </div>
                  </div>
                </div>

                {/* Category breakdown — only show categories visible in photos */}
                {(() => {
                  const cats = (['kitchen', 'bathroom', 'floors', 'exterior'] as const)
                    .filter((cat) => listing.condition_details![cat] != null);
                  if (cats.length === 0) return null;
                  return (
                    <div className="space-y-2">
                      {cats.map((cat) => {
                        const score = listing.condition_details![cat] as number;
                        return (
                          <div key={cat} className="space-y-1">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2 text-sm">
                                <span>{conditionCategoryIcons[cat]}</span>
                                <span className="capitalize">{cat}</span>
                              </div>
                              <span className={`text-sm font-bold ${getConditionColor(score)}`}>
                                {score.toFixed(1)}<span className="text-muted-foreground font-normal">/10</span>
                              </span>
                            </div>
                            <div className="relative h-1.5 rounded-full bg-muted overflow-hidden">
                              <div
                                className={`absolute inset-y-0 left-0 rounded-full transition-all ${getConditionBg(score)}`}
                                style={{ width: `${score * 10}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}

                {/* AI Notes */}
                {listing.condition_details.notes && (
                  <div className="rounded-lg bg-muted/30 p-3 border border-muted">
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {listing.condition_details.notes}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Market Context */}
          {marketData && (marketData.mortgage_rate != null || marketData.policy_rate != null) && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Market Context
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  {marketData.mortgage_rate != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">5yr Mortgage</span>
                        {marketData.mortgage_direction === 'up' ? (
                          <TrendingUp className="h-3 w-3 text-red-500" />
                        ) : marketData.mortgage_direction === 'down' ? (
                          <TrendingDown className="h-3 w-3 text-green-500" />
                        ) : (
                          <Minus className="h-3 w-3 text-muted-foreground" />
                        )}
                      </div>
                      <div className="text-lg font-bold">{marketData.mortgage_rate.toFixed(2)}%</div>
                    </div>
                  )}
                  {marketData.policy_rate != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">BoC Policy</span>
                        {marketData.policy_direction === 'up' ? (
                          <TrendingUp className="h-3 w-3 text-red-500" />
                        ) : marketData.policy_direction === 'down' ? (
                          <TrendingDown className="h-3 w-3 text-green-500" />
                        ) : (
                          <Minus className="h-3 w-3 text-muted-foreground" />
                        )}
                      </div>
                      <div className="text-lg font-bold">{marketData.policy_rate.toFixed(2)}%</div>
                    </div>
                  )}
                  {marketData.prime_rate != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">Prime Rate</div>
                      <div className="text-lg font-bold">{marketData.prime_rate.toFixed(2)}%</div>
                    </div>
                  )}
                  {marketData.cpi != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">CPI Index</div>
                      <div className="text-lg font-bold">{marketData.cpi.toFixed(1)}</div>
                    </div>
                  )}
                </div>
                {/* Mortgage impact based on real rate */}
                {marketData.mortgage_rate != null && (
                  <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 p-3 border border-blue-200 dark:border-blue-900">
                    <p className="text-xs text-muted-foreground">
                      At the current posted rate ({marketData.mortgage_rate.toFixed(2)}%), your monthly payment would be{' '}
                      <span className="font-semibold text-foreground">
                        {formatPrice(
                          (() => {
                            const r = marketData.mortgage_rate! / 100 / 12;
                            const n = 25 * 12;
                            const p = listing.price * 0.8;
                            return p * (r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
                          })()
                        )}
                      </span>
                      {' '}(20% down, 25yr amortization)
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Rental Market Intelligence */}
          {rentTrend && rentTrend.current_rent != null && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Home className="h-4 w-4" />
                  Rental Market
                  <span className="text-xs text-muted-foreground font-normal ml-auto">
                    CMHC {rentTrend.zone}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-muted/50">
                    <div className="text-xs text-muted-foreground mb-1">
                      Avg Rent ({rentTrend.bedroom_type})
                    </div>
                    <div className="text-lg font-bold">
                      {formatPrice(rentTrend.current_rent)}/mo
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-muted/50">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-muted-foreground">
                        {rentTrend.cagr_5yr != null ? 'CAGR 5yr' : 'Annual Growth'}
                      </span>
                      {rentTrend.growth_direction === 'accelerating' ? (
                        <TrendingUp className="h-3 w-3 text-orange-500" />
                      ) : rentTrend.growth_direction === 'decelerating' ? (
                        <TrendingDown className="h-3 w-3 text-blue-500" />
                      ) : (
                        <Minus className="h-3 w-3 text-muted-foreground" />
                      )}
                    </div>
                    <div className="text-lg font-bold">
                      {rentTrend.cagr_5yr != null
                        ? `${rentTrend.cagr_5yr > 0 ? '+' : ''}${rentTrend.cagr_5yr}%`
                        : rentTrend.annual_growth_rate != null
                          ? `${rentTrend.annual_growth_rate > 0 ? '+' : ''}${rentTrend.annual_growth_rate}%`
                          : '—'}
                    </div>
                    {rentTrend.cagr_5yr != null && rentTrend.annual_growth_rate != null && (
                      <div className="text-[10px] text-muted-foreground">
                        Linear: {rentTrend.annual_growth_rate > 0 ? '+' : ''}{rentTrend.annual_growth_rate}%/yr
                      </div>
                    )}
                  </div>
                  {rentTrend.vacancy_rate != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">Vacancy Rate</span>
                        {rentTrend.vacancy_direction === 'up' ? (
                          <TrendingUp className="h-3 w-3 text-red-500" />
                        ) : rentTrend.vacancy_direction === 'down' ? (
                          <TrendingDown className="h-3 w-3 text-green-500" />
                        ) : (
                          <Minus className="h-3 w-3 text-muted-foreground" />
                        )}
                      </div>
                      <div className="text-lg font-bold">{rentTrend.vacancy_rate.toFixed(1)}%</div>
                    </div>
                  )}
                  {rentTrend.forecasts.length > 0 && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">
                        {rentTrend.forecasts[0].year} Forecast
                      </div>
                      <div className="text-lg font-bold">
                        {formatPrice(rentTrend.forecasts[0].projected_rent)}/mo
                      </div>
                    </div>
                  )}
                </div>

                {/* Rent trend chart with forecast */}
                {rentTrend.rents.length >= 3 && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-2">Rent Trend</div>
                    <div className="h-44">
                      <ResponsiveContainer width="100%" height="100%">
                        {(() => {
                          const historyData = rentTrend.years.slice(-8).map((yr, i) => ({
                            year: yr,
                            rent: Math.round(rentTrend.rents.slice(-8)[i]),
                          }));
                          const forecastData = rentTrend.forecasts.map(f => ({
                            year: f.year,
                            forecast: Math.round(f.projected_rent),
                            forecastLower: Math.round(f.lower_bound),
                            forecastUpper: Math.round(f.upper_bound),
                          }));
                          // Bridge: last history point starts the forecast line
                          const lastHistory = historyData[historyData.length - 1];
                          const bridgedForecast = lastHistory
                            ? [{ year: lastHistory.year, forecast: lastHistory.rent, forecastLower: lastHistory.rent, forecastUpper: lastHistory.rent }, ...forecastData]
                            : forecastData;
                          const chartData = historyData.map(d => ({
                            ...d,
                            ...bridgedForecast.find(f => f.year === d.year),
                          }));
                          bridgedForecast.forEach(f => {
                            if (!chartData.find(d => d.year === f.year)) {
                              chartData.push({ ...f, rent: undefined as unknown as number });
                            }
                          });
                          chartData.sort((a, b) => a.year - b.year);

                          const perUnitRent = listing.estimated_rent && listing.units
                            ? Math.round(listing.estimated_rent / listing.units)
                            : null;

                          return (
                            <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
                              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                              <XAxis
                                dataKey="year"
                                tick={{ fontSize: 10 }}
                                tickFormatter={(v) => String(v).slice(-2)}
                                className="text-muted-foreground"
                              />
                              <YAxis
                                tick={{ fontSize: 10 }}
                                tickFormatter={(v) => `$${v}`}
                                className="text-muted-foreground"
                                domain={['auto', 'auto']}
                              />
                              <Tooltip
                                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid hsl(var(--border))', background: 'hsl(var(--popover))' }}
                                formatter={(value, name) => {
                                  const label = name === 'rent' ? 'Avg Rent' : name === 'forecast' ? 'Forecast' : String(name);
                                  return [`$${value}/mo`, label];
                                }}
                                labelFormatter={(label) => `${label}`}
                              />
                              {/* Forecast confidence band */}
                              <Area
                                type="monotone"
                                dataKey="forecastUpper"
                                stroke="none"
                                fill="hsl(var(--primary))"
                                fillOpacity={0.08}
                                connectNulls={false}
                              />
                              <Area
                                type="monotone"
                                dataKey="forecastLower"
                                stroke="none"
                                fill="hsl(var(--background))"
                                fillOpacity={1}
                                connectNulls={false}
                              />
                              {/* Historical rent */}
                              <Area
                                type="monotone"
                                dataKey="rent"
                                stroke="hsl(var(--primary))"
                                fill="hsl(var(--primary))"
                                fillOpacity={0.15}
                                strokeWidth={2}
                                dot={{ r: 3, fill: 'hsl(var(--primary))' }}
                                connectNulls={false}
                              />
                              {/* Forecast line */}
                              <Area
                                type="monotone"
                                dataKey="forecast"
                                stroke="hsl(var(--primary))"
                                fill="none"
                                strokeWidth={2}
                                strokeDasharray="5 3"
                                dot={{ r: 3, fill: 'hsl(var(--primary))', strokeDasharray: '' }}
                                connectNulls={false}
                              />
                              {/* Property's rent reference line */}
                              {perUnitRent && (
                                <ReferenceLine
                                  y={perUnitRent}
                                  stroke="hsl(var(--chart-2))"
                                  strokeDasharray="3 3"
                                  label={{ value: `Your rent: $${perUnitRent}`, position: 'insideTopRight', fontSize: 10, fill: 'hsl(var(--chart-2))' }}
                                />
                              )}
                            </AreaChart>
                          );
                        })()}
                      </ResponsiveContainer>
                    </div>
                    {rentTrend.forecasts.length > 0 && (
                      <div className="text-[10px] text-muted-foreground mt-1">
                        Dashed line = linear forecast (
                        {rentTrend.forecasts[0]?.year}&ndash;{rentTrend.forecasts[rentTrend.forecasts.length - 1]?.year}
                        )
                      </div>
                    )}
                  </div>
                )}

                {/* Comparison with property's estimated rent */}
                {listing.estimated_rent && rentTrend.current_rent != null && listing.units > 0 && (
                  <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3 border border-green-200 dark:border-green-900">
                    <p className="text-xs text-muted-foreground">
                      This property&apos;s estimated rent is{' '}
                      <span className="font-semibold text-foreground">
                        {(() => {
                          const perUnit = listing.estimated_rent! / listing.units;
                          const diff = ((perUnit - rentTrend.current_rent!) / rentTrend.current_rent!) * 100;
                          return `${diff > 0 ? '+' : ''}${diff.toFixed(0)}%`;
                        })()}
                      </span>
                      {' '}vs zone average ({formatPrice(rentTrend.current_rent)}/unit)
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Neighbourhood Profile (Demographics) */}
          {demographics && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  Neighbourhood Profile
                  <span className="text-xs text-muted-foreground font-normal ml-auto">
                    Census 2021 — {demographics.municipality}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  {demographics.median_household_income != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">Median Income</div>
                      <div className="text-lg font-bold">{formatPrice(demographics.median_household_income)}</div>
                      <div className="text-[10px] text-muted-foreground">per household/yr</div>
                    </div>
                  )}
                  {demographics.population != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">Population</div>
                      <div className="text-lg font-bold">
                        {demographics.population >= 1000000
                          ? `${(demographics.population / 1000000).toFixed(1)}M`
                          : demographics.population >= 1000
                            ? `${(demographics.population / 1000).toFixed(0)}K`
                            : demographics.population.toLocaleString()}
                      </div>
                      {demographics.pop_change_pct != null && (
                        <div className="flex items-center gap-1 text-[10px]">
                          {demographics.pop_change_pct > 0 ? (
                            <TrendingUp className="h-2.5 w-2.5 text-green-500" />
                          ) : demographics.pop_change_pct < 0 ? (
                            <TrendingDown className="h-2.5 w-2.5 text-red-500" />
                          ) : (
                            <Minus className="h-2.5 w-2.5 text-muted-foreground" />
                          )}
                          <span className={demographics.pop_change_pct > 0 ? 'text-green-600' : demographics.pop_change_pct < 0 ? 'text-red-600' : 'text-muted-foreground'}>
                            {demographics.pop_change_pct > 0 ? '+' : ''}{demographics.pop_change_pct.toFixed(1)}% since 2016
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                  {demographics.avg_household_size != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">Avg Household Size</div>
                      <div className="text-lg font-bold">{demographics.avg_household_size.toFixed(1)}</div>
                      <div className="text-[10px] text-muted-foreground">persons</div>
                    </div>
                  )}
                  {demographics.total_households != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">Total Households</div>
                      <div className="text-lg font-bold">
                        {demographics.total_households >= 1000
                          ? `${(demographics.total_households / 1000).toFixed(0)}K`
                          : demographics.total_households.toLocaleString()}
                      </div>
                    </div>
                  )}
                </div>

                {/* Rent-to-Income Ratio gauge */}
                {demographics.rent_to_income_ratio != null && (
                  <div className="rounded-lg p-3 border bg-muted/30">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-muted-foreground">Rent-to-Income Ratio</span>
                      <span className={`text-sm font-bold ${
                        demographics.rent_to_income_ratio < 25 ? 'text-green-600' :
                        demographics.rent_to_income_ratio <= 30 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {demographics.rent_to_income_ratio.toFixed(1)}%
                      </span>
                    </div>
                    <div className="relative h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`absolute inset-y-0 left-0 rounded-full transition-all ${
                          demographics.rent_to_income_ratio < 25 ? 'bg-green-500' :
                          demographics.rent_to_income_ratio <= 30 ? 'bg-yellow-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${Math.min(demographics.rent_to_income_ratio / 50 * 100, 100)}%` }}
                      />
                      {/* 30% threshold marker */}
                      <div
                        className="absolute top-0 w-0.5 h-2 bg-foreground/50"
                        style={{ left: '60%' }}
                        title="30% affordability threshold"
                      />
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                      <span>Affordable</span>
                      <span>30% threshold</span>
                      <span>Strained</span>
                    </div>
                  </div>
                )}

                {/* Income comparison with CMA average */}
                {demographics.median_household_income != null && (
                  <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 p-3 border border-blue-200 dark:border-blue-900">
                    <p className="text-xs text-muted-foreground">
                      Median after-tax income:{' '}
                      <span className="font-semibold text-foreground">
                        {demographics.median_after_tax_income != null
                          ? formatPrice(demographics.median_after_tax_income)
                          : 'N/A'}
                      </span>
                      {demographics.avg_household_income != null && (
                        <> | Avg household income:{' '}
                          <span className="font-semibold text-foreground">
                            {formatPrice(demographics.avg_household_income)}
                          </span>
                        </>
                      )}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Safety & Development */}
          {neighbourhood && (neighbourhood.crime || neighbourhood.permits || neighbourhood.tax) && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  Safety & Development
                  <span className="text-xs text-muted-foreground font-normal ml-auto">
                    {neighbourhood.borough} ({neighbourhood.year})
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  {/* Safety Score */}
                  {neighbourhood.safety_score != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">Safety Score</div>
                      <div className="flex items-center gap-2">
                        <div className={`text-lg font-bold ${
                          neighbourhood.safety_score >= 7 ? 'text-green-600' :
                          neighbourhood.safety_score >= 4 ? 'text-yellow-600' : 'text-red-600'
                        }`}>
                          {neighbourhood.safety_score.toFixed(1)}<span className="text-muted-foreground font-normal text-xs">/10</span>
                        </div>
                      </div>
                      <div className="relative h-1.5 rounded-full bg-muted overflow-hidden mt-1">
                        <div
                          className={`absolute inset-y-0 left-0 rounded-full transition-all ${
                            neighbourhood.safety_score >= 7 ? 'bg-green-500' :
                            neighbourhood.safety_score >= 4 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${neighbourhood.safety_score * 10}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Gentrification Signal */}
                  {neighbourhood.gentrification_signal && neighbourhood.gentrification_signal !== 'none' && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">Gentrification</div>
                      <Badge variant="outline" className={`text-xs ${
                        neighbourhood.gentrification_signal === 'early' ? 'border-blue-300 text-blue-600' :
                        neighbourhood.gentrification_signal === 'mid' ? 'border-orange-300 text-orange-600' :
                        'border-purple-300 text-purple-600'
                      }`}>
                        {neighbourhood.gentrification_signal === 'early' ? 'Early Stage' :
                         neighbourhood.gentrification_signal === 'mid' ? 'Mid Stage' : 'Mature'}
                      </Badge>
                      <div className="text-[10px] text-muted-foreground mt-1">Based on permit activity</div>
                    </div>
                  )}

                  {/* Crime stats */}
                  {neighbourhood.crime && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">Crime Incidents</span>
                        {neighbourhood.crime.year_over_year_change_pct != null && (
                          neighbourhood.crime.year_over_year_change_pct < -2 ? (
                            <TrendingDown className="h-3 w-3 text-green-500" />
                          ) : neighbourhood.crime.year_over_year_change_pct > 2 ? (
                            <TrendingUp className="h-3 w-3 text-red-500" />
                          ) : (
                            <Minus className="h-3 w-3 text-muted-foreground" />
                          )
                        )}
                      </div>
                      <div className="text-lg font-bold">{neighbourhood.crime.total_crimes.toLocaleString()}</div>
                      {neighbourhood.crime.year_over_year_change_pct != null && (
                        <div className={`text-[10px] ${
                          neighbourhood.crime.year_over_year_change_pct < 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {neighbourhood.crime.year_over_year_change_pct > 0 ? '+' : ''}
                          {neighbourhood.crime.year_over_year_change_pct.toFixed(1)}% YoY
                        </div>
                      )}
                    </div>
                  )}

                  {/* Permit activity */}
                  {neighbourhood.permits && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">
                        <Hammer className="h-3 w-3 inline mr-1" />
                        Permits
                      </div>
                      <div className="text-lg font-bold">{neighbourhood.permits.total_permits.toLocaleString()}</div>
                      <div className="text-[10px] text-muted-foreground">
                        {neighbourhood.permits.transform_permits} reno | {neighbourhood.permits.construction_permits} new
                      </div>
                    </div>
                  )}
                </div>

                {/* Tax rate info */}
                {neighbourhood.tax && (
                  <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 p-3 border border-blue-200 dark:border-blue-900">
                    <p className="text-xs text-muted-foreground">
                      Tax rate: <span className="font-semibold text-foreground">${neighbourhood.tax.residential_rate.toFixed(4)}/$100</span> (residential)
                      {neighbourhood.tax.annual_tax_estimate != null && (
                        <> | Est. annual tax: <span className="font-semibold text-foreground">{formatPrice(neighbourhood.tax.annual_tax_estimate)}</span></>
                      )}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Property Details (collapsed) */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Home className="h-4 w-4" />
                Property Details
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-3 gap-3 text-sm">
              <div className="text-center p-2 rounded bg-muted/50">
                <div className="text-lg font-bold">{listing.units}</div>
                <div className="text-xs text-muted-foreground">Units</div>
              </div>
              <div className="text-center p-2 rounded bg-muted/50">
                <div className="text-lg font-bold">{listing.bedrooms}</div>
                <div className="text-xs text-muted-foreground">Beds</div>
              </div>
              <div className="text-center p-2 rounded bg-muted/50">
                <div className="text-lg font-bold">{listing.bathrooms}</div>
                <div className="text-xs text-muted-foreground">Baths</div>
              </div>
              {listing.sqft && (
                <div className="text-center p-2 rounded bg-muted/50">
                  <div className="text-lg font-bold">{(listing.sqft / 1000).toFixed(1)}k</div>
                  <div className="text-xs text-muted-foreground">sqft</div>
                </div>
              )}
              {listing.year_built && (
                <div className="text-center p-2 rounded bg-muted/50">
                  <div className="text-lg font-bold">{listing.year_built}</div>
                  <div className="text-xs text-muted-foreground">Built</div>
                </div>
              )}
              <div className="text-center p-2 rounded bg-muted/50">
                <div className="text-lg font-bold">
                  <Badge variant="outline" className="text-xs">
                    {getPropertyTypeLabel(listing.property_type)}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground">Type</div>
              </div>
            </CardContent>
          </Card>
        </div>
      </SheetContent>
    </Sheet>
  );
}
