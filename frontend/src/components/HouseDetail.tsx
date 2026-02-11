'use client';

import { useEffect, useState } from 'react';
import {
  ExternalLink, AlertTriangle, Footprints, Bus, Bike, ChevronLeft, ChevronRight,
  DollarSign, Shield, Users, Sparkles, Hammer, Building, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { useTranslation } from '@/i18n/LanguageContext';
import { formatPrice, formatNumber } from '@/lib/formatters';
import { propertiesApi, marketApi } from '@/lib/api';
import type { HouseWithScore, PropertyListing, PriceHistoryResponse, DemographicProfile, NeighbourhoodResponse } from '@/lib/types';

interface HouseDetailProps {
  house: HouseWithScore | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function getBadgeColor(score: number): string {
  if (score >= 70) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
}

function getWalkScoreColor(score: number | null): string {
  if (score == null) return 'text-muted-foreground';
  if (score >= 70) return 'text-green-600';
  if (score >= 50) return 'text-yellow-600';
  return 'text-red-600';
}

function getWalkScoreBg(score: number | null): string {
  if (score == null) return 'bg-muted';
  if (score >= 70) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
}

function getConditionColor(score: number): string {
  if (score >= 7) return 'text-green-600';
  if (score >= 5) return 'text-yellow-600';
  return 'text-red-600';
}

function getConditionBg(score: number): string {
  if (score >= 7) return 'bg-green-500';
  if (score >= 5) return 'bg-yellow-500';
  return 'bg-red-500';
}

/** Circular progress visualization for pillar scores */
function CircularScore({ value, max, label, colorClass }: { value: number; max: number; label: string; colorClass: string }) {
  const pct = Math.min(100, (value / max) * 100);
  const circumference = 2 * Math.PI * 36;
  const strokeDashoffset = circumference - (pct / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="36" fill="none" stroke="currentColor" strokeWidth="6" className="text-muted" />
          <circle
            cx="40" cy="40" r="36" fill="none" strokeWidth="6"
            stroke="currentColor"
            className={colorClass}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold tabular-nums">{value.toFixed(0)}/{max}</span>
        </div>
      </div>
      <span className="text-xs font-medium text-center">{label}</span>
    </div>
  );
}

function SubScoreRow({ label, value }: { label: string; value: number | null }) {
  const { t } = useTranslation();
  if (value == null) return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-muted-foreground">{t('houses.dataNotAvailable')}</span>
    </div>
  );
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value.toFixed(1)}</span>
    </div>
  );
}

function CostRow({ label, value, locale, bold }: { label: string; value: number | null; locale: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between text-sm ${bold ? 'font-semibold' : ''}`}>
      <span className={bold ? '' : 'text-muted-foreground'}>{label}</span>
      <span className="tabular-nums">
        {value != null ? formatPrice(value, locale as 'en' | 'fr') : '-'}
      </span>
    </div>
  );
}

export function HouseDetail({ house, open, onOpenChange }: HouseDetailProps) {
  const { t, locale } = useTranslation();
  const [photoIndex, setPhotoIndex] = useState(0);
  const [enrichedListing, setEnrichedListing] = useState<PropertyListing | null>(null);
  const [priceHistory, setPriceHistory] = useState<PriceHistoryResponse | null>(null);
  const [demographics, setDemographics] = useState<DemographicProfile | null>(null);
  const [neighbourhood, setNeighbourhood] = useState<NeighbourhoodResponse | null>(null);

  const intlLocale = locale === 'fr' ? 'fr-CA' : 'en-CA';

  useEffect(() => {
    if (!house) {
      setEnrichedListing(null);
      setPriceHistory(null);
      setDemographics(null);
      setNeighbourhood(null);
      return;
    }

    let cancelled = false;
    const { listing } = house;

    // Fetch full details (triggers on-demand condition scoring + walk score)
    propertiesApi.getDetails(listing.id).then((detail) => {
      if (!cancelled) setEnrichedListing(detail);
    }).catch(() => {});

    propertiesApi.getPriceHistory(listing.id).then((data) => {
      if (!cancelled) setPriceHistory(data);
    }).catch(() => {});

    const cityName = listing.city || 'Montreal';
    marketApi.demographics(cityName).then((data) => {
      if (!cancelled) setDemographics(data);
    }).catch(() => {});

    const assessmentVal = listing.municipal_assessment || undefined;
    const postalCode = listing.postal_code || undefined;
    marketApi.neighbourhood(cityName, assessmentVal, postalCode).then((data) => {
      if (!cancelled) setNeighbourhood(data);
    }).catch(() => {});

    return () => { cancelled = true; };
  }, [house?.listing.id]);

  if (!house) return null;

  const { family_metrics: fm } = house;
  // Use enriched listing (with condition score, walk score, photos) when available
  const listing = enrichedListing ?? house.listing;
  const photos = listing.photo_urls ?? [];

  const monthlyTotal =
    (fm.estimated_monthly_mortgage ?? 0) +
    (fm.estimated_monthly_taxes ?? 0) +
    (fm.estimated_annual_energy != null ? fm.estimated_annual_energy / 12 : 0) +
    (fm.estimated_annual_insurance != null ? fm.estimated_annual_insurance / 12 : 0);

  const getWalkLabel = (score: number) => {
    if (score >= 90) return t('detail.walkParadise');
    if (score >= 70) return t('detail.veryWalkable');
    if (score >= 50) return t('detail.somewhatWalkable');
    if (score >= 25) return t('detail.carDependent');
    return t('detail.almostAllCar');
  };

  const getConditionLabel = (score: number) => {
    if (score >= 8) return t('detail.conditionExcellent');
    if (score >= 6) return t('detail.conditionGood');
    if (score >= 4) return t('detail.conditionFair');
    return t('detail.conditionPoor');
  };

  const conditionCategoryIcons: Record<string, string> = {
    kitchen: '🍳', bathroom: '🚿', floors: '🏠', exterior: '🏢',
  };
  const conditionCategoryLabels: Record<string, string> = {
    kitchen: t('detail.kitchen'), bathroom: t('detail.bathroom'),
    floors: t('detail.floors'), exterior: t('detail.exterior'),
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-xl md:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="text-left">{listing.address}</SheetTitle>
          <SheetDescription className="text-left">{listing.city}</SheetDescription>
        </SheetHeader>

        <div className="mt-4 space-y-6">
          {/* 1. Header: Photo + Price + Score */}
          <div className="space-y-3">
            {photos.length > 0 ? (
              <div className="relative rounded-lg overflow-hidden bg-muted h-56">
                <img
                  src={photos[photoIndex]}
                  alt={`${listing.address} - ${photoIndex + 1}`}
                  className="w-full h-full object-cover"
                />
                {photos.length > 1 && (
                  <>
                    <button
                      className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/50 text-white rounded-full p-1 hover:bg-black/70"
                      onClick={() => setPhotoIndex((i) => (i - 1 + photos.length) % photos.length)}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <button
                      className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/50 text-white rounded-full p-1 hover:bg-black/70"
                      onClick={() => setPhotoIndex((i) => (i + 1) % photos.length)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/50 text-white text-xs px-2 py-0.5 rounded-full">
                      {photoIndex + 1} / {photos.length}
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="rounded-lg bg-muted h-32 flex items-center justify-center text-muted-foreground text-sm">
                {t('houses.noPhoto')}
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold">{formatPrice(listing.price, locale as 'en' | 'fr')}</span>
              <div className={`rounded-full w-14 h-14 flex items-center justify-center text-lg font-bold text-white shadow-lg ${getBadgeColor(fm.family_score)}`}>
                {fm.family_score.toFixed(0)}
              </div>
            </div>
            <p className="text-sm text-muted-foreground">{t('houses.familyScore')}</p>
          </div>

          <Separator />

          {/* 2. Score Breakdown */}
          <div>
            <h3 className="text-sm font-semibold mb-3">{t('detail.scoreBreakdown')}</h3>
            <div className="grid grid-cols-3 gap-4">
              <Card>
                <CardContent className="p-3 space-y-2">
                  <CircularScore value={fm.livability_score} max={40} label={t('houses.livability')} colorClass="text-blue-500" />
                  <div className="space-y-1">
                    <SubScoreRow label={t('houses.walkScore')} value={fm.walk_score_pts} />
                    <SubScoreRow label={t('houses.transitScore')} value={fm.transit_score_pts} />
                    <SubScoreRow label={t('houses.safety')} value={fm.safety_pts} />
                    <SubScoreRow label={t('houses.schoolProximity')} value={fm.school_proximity_pts} />
                    <SubScoreRow label={t('houses.parks')} value={fm.parks_pts} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-3 space-y-2">
                  <CircularScore value={fm.value_score} max={35} label={t('houses.value')} colorClass="text-green-500" />
                  <div className="space-y-1">
                    <SubScoreRow label={t('houses.priceVsAssessment')} value={fm.price_vs_assessment_pts} />
                    <SubScoreRow label={t('houses.pricePerSqft')} value={fm.price_per_sqft_pts} />
                    <SubScoreRow label={t('houses.affordability')} value={fm.affordability_pts} />
                    <SubScoreRow label={t('houses.marketTrajectory')} value={fm.market_trajectory_pts} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-3 space-y-2">
                  <CircularScore value={fm.space_score} max={25} label={t('houses.spaceComfort')} colorClass="text-purple-500" />
                  <div className="space-y-1">
                    <SubScoreRow label={t('houses.lotSize')} value={fm.lot_size_pts} />
                    <SubScoreRow label={t('houses.bedrooms')} value={fm.bedroom_pts} />
                    <SubScoreRow label={t('houses.condition')} value={fm.condition_pts} />
                    <SubScoreRow label={t('houses.propertyAge')} value={fm.age_pts} />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Data completeness indicator */}
            {fm.data_completeness && (() => {
              const fields = Object.entries(fm.data_completeness);
              const available = fields.filter(([, v]) => v).length;
              const total = fields.length;
              const pct = total > 0 ? Math.round((available / total) * 100) : 0;
              const missing = fields.filter(([, v]) => !v).map(([k]) => k);
              if (pct >= 100) return null;
              return (
                <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 px-3 py-2">
                  <p className="text-xs text-amber-700 dark:text-amber-400">
                    {t('houses.dataCompleteness', { pct: String(pct), available: String(available), total: String(total) })}
                  </p>
                  {missing.length > 0 && (
                    <p className="text-xs text-amber-600 dark:text-amber-500 mt-0.5">
                      {t('houses.missingData')}: {missing.map(k => t(`houses.field_${k}`)).join(', ')}
                    </p>
                  )}
                </div>
              );
            })()}
          </div>

          <Separator />

          {/* 3. Cost of Ownership */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t('houses.costOfOwnership')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <CostRow label={t('houses.monthlyMortgage')} value={fm.estimated_monthly_mortgage} locale={locale} />
              <CostRow label={t('houses.monthlyTaxes')} value={fm.estimated_monthly_taxes} locale={locale} />
              <CostRow label={t('houses.annualEnergy')} value={fm.estimated_annual_energy != null ? fm.estimated_annual_energy / 12 : null} locale={locale} />
              <CostRow label={t('houses.annualInsurance')} value={fm.estimated_annual_insurance != null ? fm.estimated_annual_insurance / 12 : null} locale={locale} />
              <Separator />
              <CostRow label={t('houses.totalMonthlyCost')} value={monthlyTotal > 0 ? monthlyTotal : null} locale={locale} bold />
              <Separator />
              <CostRow label={t('houses.welcomeTax')} value={fm.welcome_tax} locale={locale} />
              <CostRow label={t('houses.totalCashNeeded')} value={fm.total_cash_needed} locale={locale} bold />
            </CardContent>
          </Card>

          {/* 4. Property Details */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t('detail.propertyDetails')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('houses.bedrooms')}</span>
                  <span className="font-medium">{listing.bedrooms}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('common.baths')}</span>
                  <span className="font-medium">{listing.bathrooms}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('common.sqft')}</span>
                  <span className="font-medium">{listing.sqft ? formatNumber(listing.sqft, locale as 'en' | 'fr') : '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('houses.lotSize')}</span>
                  <span className="font-medium">{listing.lot_sqft ? formatNumber(listing.lot_sqft, locale as 'en' | 'fr') : '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('common.built')}</span>
                  <span className="font-medium">{listing.year_built ?? '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('detail.assessment')}</span>
                  <span className="font-medium">{listing.municipal_assessment ? formatPrice(listing.municipal_assessment, locale as 'en' | 'fr') : '-'}</span>
                </div>
                {fm.price_per_sqft != null && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t('houses.pricePerSqft')}</span>
                    <span className="font-medium">{formatPrice(fm.price_per_sqft, locale as 'en' | 'fr')}/{t('common.sqft')}</span>
                  </div>
                )}
              </div>

              {/* Walk / Transit / Bike scores with labels + progress bars */}
              {(listing.walk_score != null || listing.transit_score != null || listing.bike_score != null) && (
                <div className="mt-4 space-y-3">
                  {listing.walk_score != null && (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-sm">
                          <Footprints className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>{t('detail.walkScore')}</span>
                        </div>
                        <span className={`text-sm font-bold ${getWalkScoreColor(listing.walk_score)}`}>
                          {listing.walk_score}
                        </span>
                      </div>
                      <div className="relative h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`absolute inset-y-0 left-0 rounded-full transition-all ${getWalkScoreBg(listing.walk_score)}`}
                          style={{ width: `${listing.walk_score}%` }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">{getWalkLabel(listing.walk_score)}</p>
                    </div>
                  )}
                  {listing.transit_score != null && (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-sm">
                          <Bus className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>{t('detail.transitScore')}</span>
                        </div>
                        <span className={`text-sm font-bold ${getWalkScoreColor(listing.transit_score)}`}>
                          {listing.transit_score}
                        </span>
                      </div>
                      <div className="relative h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`absolute inset-y-0 left-0 rounded-full transition-all ${getWalkScoreBg(listing.transit_score)}`}
                          style={{ width: `${listing.transit_score}%` }}
                        />
                      </div>
                    </div>
                  )}
                  {listing.bike_score != null && (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-sm">
                          <Bike className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>{t('detail.bikeScore')}</span>
                        </div>
                        <span className={`text-sm font-bold ${getWalkScoreColor(listing.bike_score)}`}>
                          {listing.bike_score}
                        </span>
                      </div>
                      <div className="relative h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`absolute inset-y-0 left-0 rounded-full transition-all ${getWalkScoreBg(listing.bike_score)}`}
                          style={{ width: `${listing.bike_score}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* 5. AI Condition Score */}
          {listing.condition_score != null && listing.condition_details && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  {t('detail.propertyCondition')}
                  <Badge variant="outline" className="text-[10px] ml-auto font-normal gap-1">
                    <Sparkles className="h-3 w-3" />
                    {t('detail.aiAnalysis')}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
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
                          {t('detail.renoNeeded')}
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
                      <span>{t('detail.conditionPoor')}</span>
                      <span>{t('detail.conditionExcellent')}</span>
                    </div>
                  </div>
                </div>

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
                                <span>{conditionCategoryLabels[cat]}</span>
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

          {/* 6. Price History */}
          {priceHistory && priceHistory.changes.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <DollarSign className="h-4 w-4" />
                  {t('detail.priceHistory')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {priceHistory.total_change !== 0 && (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-muted-foreground">{t('detail.totalChange')}</span>
                    <span className={priceHistory.total_change < 0 ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
                      {priceHistory.total_change < 0 ? '' : '+'}{formatPrice(priceHistory.total_change, locale as 'en' | 'fr')} ({priceHistory.total_change_pct > 0 ? '+' : ''}{priceHistory.total_change_pct}%)
                    </span>
                  </div>
                )}

                <div className="h-[120px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={(() => {
                        const points: { date: string; price: number }[] = [];
                        const sorted = [...priceHistory.changes].reverse();
                        sorted.forEach((c, i) => {
                          if (i === 0) {
                            points.push({ date: new Date(c.recorded_at).toLocaleDateString(intlLocale, { month: 'short', day: 'numeric' }), price: c.old_price });
                          }
                          points.push({ date: new Date(c.recorded_at).toLocaleDateString(intlLocale, { month: 'short', day: 'numeric' }), price: c.new_price });
                        });
                        return points;
                      })()}
                      margin={{ top: 4, right: 4, bottom: 0, left: -16 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }} stroke="var(--border)" tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }} stroke="var(--border)" tickLine={false} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} domain={['auto', 'auto']} />
                      <Tooltip
                        contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--popover)', color: 'var(--popover-foreground)' }}
                        formatter={(value) => [formatPrice(value as number, locale as 'en' | 'fr'), t('detail.askingPrice')]}
                      />
                      <Line type="stepAfter" dataKey="price" stroke="var(--chart-1)" strokeWidth={2} dot={{ r: 3, fill: 'var(--chart-1)' }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="space-y-1">
                  {priceHistory.changes.map((c, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">
                        {new Date(c.recorded_at).toLocaleDateString(intlLocale, { month: 'short', day: 'numeric', year: 'numeric' })}
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="text-muted-foreground">{formatPrice(c.old_price, locale as 'en' | 'fr')}</span>
                        <span className="text-muted-foreground">&rarr;</span>
                        <span className="font-medium">{formatPrice(c.new_price, locale as 'en' | 'fr')}</span>
                        <span className={c.change < 0 ? 'text-green-600' : 'text-red-600'}>
                          ({c.change_pct > 0 ? '+' : ''}{c.change_pct}%)
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 7. Neighbourhood Profile */}
          {demographics && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  {t('detail.neighbourhoodProfile')}
                  <span className="text-xs text-muted-foreground font-normal ml-auto">
                    Census 2021 — {demographics.municipality}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  {demographics.median_household_income != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">{t('detail.medianIncome')}</div>
                      <div className="text-lg font-bold">{formatPrice(demographics.median_household_income, locale as 'en' | 'fr')}</div>
                      <div className="text-[10px] text-muted-foreground">{t('detail.perHouseholdYear')}</div>
                    </div>
                  )}
                  {demographics.population != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">{t('detail.population')}</div>
                      <div className="text-lg font-bold">
                        {demographics.population >= 1_000_000
                          ? `${(demographics.population / 1_000_000).toFixed(1)}M`
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
                            {t('detail.since2016', { pct: `${demographics.pop_change_pct > 0 ? '+' : ''}${demographics.pop_change_pct.toFixed(1)}` })}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                  {demographics.avg_household_size != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">{t('detail.avgHouseholdSize')}</div>
                      <div className="text-lg font-bold">{demographics.avg_household_size.toFixed(1)}</div>
                    </div>
                  )}
                  {demographics.total_households != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">{t('detail.totalHouseholds')}</div>
                      <div className="text-lg font-bold">
                        {demographics.total_households >= 1000
                          ? `${(demographics.total_households / 1000).toFixed(0)}K`
                          : demographics.total_households.toLocaleString()}
                      </div>
                    </div>
                  )}
                </div>

                {demographics.rent_to_income_ratio != null && (
                  <div className="rounded-lg p-3 border bg-muted/30">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-muted-foreground">{t('detail.rentToIncomeRatio')}</span>
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
                      <div className="absolute top-0 w-0.5 h-2 bg-foreground/50" style={{ left: '60%' }} title="30%" />
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                      <span>{t('detail.affordable')}</span>
                      <span>{t('detail.threshold30')}</span>
                      <span>{t('detail.strained')}</span>
                    </div>
                  </div>
                )}

                {demographics.median_household_income != null && (
                  <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 p-3 border border-blue-200 dark:border-blue-900">
                    <p className="text-xs text-muted-foreground">
                      {t('detail.medianAfterTax', {
                        amount: demographics.median_after_tax_income != null
                          ? formatPrice(demographics.median_after_tax_income, locale as 'en' | 'fr')
                          : t('common.na'),
                      })}
                      {demographics.avg_household_income != null && (
                        <> | {t('detail.avgHouseholdIncome', {
                          amount: formatPrice(demographics.avg_household_income, locale as 'en' | 'fr'),
                        })}</>
                      )}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* 8. Safety & Development */}
          {neighbourhood && (neighbourhood.crime || neighbourhood.permits || neighbourhood.housing_starts || neighbourhood.tax) && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  {t('detail.safetyDevelopment')}
                  <span className="text-xs text-muted-foreground font-normal ml-auto">
                    {neighbourhood.borough} ({neighbourhood.year})
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  {neighbourhood.safety_score != null && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">{t('detail.safetyScore')}</div>
                      <div className={`text-lg font-bold ${
                        neighbourhood.safety_score >= 7 ? 'text-green-600' :
                        neighbourhood.safety_score >= 4 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {neighbourhood.safety_score.toFixed(1)}<span className="text-muted-foreground font-normal text-xs">/10</span>
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

                  {neighbourhood.gentrification_signal && neighbourhood.gentrification_signal !== 'none' && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">{t('detail.gentrification')}</div>
                      <Badge variant="outline" className={`text-xs ${
                        neighbourhood.gentrification_signal === 'early' ? 'border-blue-300 text-blue-600' :
                        neighbourhood.gentrification_signal === 'mid' ? 'border-orange-300 text-orange-600' :
                        'border-purple-300 text-purple-600'
                      }`}>
                        {neighbourhood.gentrification_signal === 'early' ? t('detail.earlyStage') :
                         neighbourhood.gentrification_signal === 'mid' ? t('detail.midStage') : t('detail.mature')}
                      </Badge>
                      <div className="text-[10px] text-muted-foreground mt-1">{t('detail.basedOnPermits')}</div>
                    </div>
                  )}

                  {neighbourhood.crime && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">{t('detail.crimeIncidents')}</span>
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
                        <div className={`text-[10px] ${neighbourhood.crime.year_over_year_change_pct < 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {t('detail.yoy', { pct: `${neighbourhood.crime.year_over_year_change_pct > 0 ? '+' : ''}${neighbourhood.crime.year_over_year_change_pct.toFixed(1)}` })}
                        </div>
                      )}
                    </div>
                  )}

                  {neighbourhood.permits && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">
                        <Hammer className="h-3 w-3 inline mr-1" />
                        {t('detail.permits')}
                      </div>
                      <div className="text-lg font-bold">{neighbourhood.permits.total_permits.toLocaleString()}</div>
                      <div className="text-[10px] text-muted-foreground">
                        {t('detail.reno', { count: neighbourhood.permits.transform_permits })} | {t('detail.newConstruction', { count: neighbourhood.permits.construction_permits })}
                      </div>
                    </div>
                  )}

                  {neighbourhood.housing_starts && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="text-xs text-muted-foreground mb-1">
                        <Building className="h-3 w-3 inline mr-1" />
                        {t('detail.housingStarts')}
                      </div>
                      <div className="text-lg font-bold">{neighbourhood.housing_starts.total.toLocaleString()}</div>
                      <div className="text-[10px] text-muted-foreground">
                        {t('detail.startsBreakdown', {
                          single: neighbourhood.housing_starts.single,
                          semi: neighbourhood.housing_starts.semi,
                          row: neighbourhood.housing_starts.row,
                          apartment: neighbourhood.housing_starts.apartment,
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {neighbourhood.tax && (
                  <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 p-3 border border-blue-200 dark:border-blue-900 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground">{t('detail.taxRate_label')}</span>
                      {neighbourhood.tax.yoy_change_pct != null && (
                        <Badge variant={neighbourhood.tax.yoy_change_pct <= 0 ? 'default' : 'destructive'} className="text-[10px] h-5">
                          {neighbourhood.tax.yoy_change_pct > 0 ? <TrendingUp className="h-3 w-3 mr-0.5" /> : <TrendingDown className="h-3 w-3 mr-0.5" />}
                          {neighbourhood.tax.yoy_change_pct > 0 ? '+' : ''}{neighbourhood.tax.yoy_change_pct.toFixed(1)}% YOY
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-lg font-bold">{neighbourhood.tax.residential_rate.toFixed(4)}</span>
                      <span className="text-xs text-muted-foreground">/$100</span>
                      {neighbourhood.tax.annual_tax_estimate != null && (
                        <span className="text-xs text-muted-foreground ml-auto">
                          {t('detail.estAnnualTax', { amount: formatPrice(neighbourhood.tax.annual_tax_estimate, locale as 'en' | 'fr') })}
                        </span>
                      )}
                    </div>
                    {neighbourhood.tax.rank != null && neighbourhood.tax.total_boroughs != null && (
                      <p className="text-[10px] text-muted-foreground">
                        {t('detail.taxRank', { rank: neighbourhood.tax.rank, total: neighbourhood.tax.total_boroughs })}
                        {neighbourhood.tax.city_avg_rate != null && (
                          <> ({t('detail.cityAvg', { rate: neighbourhood.tax.city_avg_rate.toFixed(4) })})</>
                        )}
                      </p>
                    )}
                    {neighbourhood.tax.cagr_5yr != null && (
                      <p className="text-[10px] text-muted-foreground">
                        {t('detail.taxCagr', { pct: `${neighbourhood.tax.cagr_5yr > 0 ? '+' : ''}${neighbourhood.tax.cagr_5yr.toFixed(1)}` })}
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* 9. Risk Flags */}
          {(fm.flood_zone || fm.contaminated_nearby) && (
            <div className="space-y-2">
              {fm.flood_zone && (
                <div className="flex items-center gap-2 rounded-md bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-3">
                  <AlertTriangle className="h-4 w-4 text-red-600" />
                  <span className="text-sm text-red-800 dark:text-red-300">{t('houses.floodZoneWarning')}</span>
                </div>
              )}
              {fm.contaminated_nearby && (
                <div className="flex items-center gap-2 rounded-md bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-3">
                  <AlertTriangle className="h-4 w-4 text-red-600" />
                  <span className="text-sm text-red-800 dark:text-red-300">{t('houses.contaminatedWarning')}</span>
                </div>
              )}
            </div>
          )}

          {fm.flood_zone == null && fm.contaminated_nearby == null && (
            <div className="rounded-md bg-muted/50 border p-3">
              <span className="text-sm text-muted-foreground">{t('houses.dataNotAvailable')}</span>
            </div>
          )}

          {/* 10. Action buttons */}
          <div className="flex gap-3">
            <Button asChild className="flex-1">
              <a href={listing.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                {t('houses.viewOnCentris')}
              </a>
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
