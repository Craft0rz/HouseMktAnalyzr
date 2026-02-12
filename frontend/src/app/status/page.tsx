'use client';

import { useState } from 'react';
import { Play, CheckCircle2, XCircle, AlertTriangle, Clock, Loader2, MapPin } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { LoadingCard } from '@/components/LoadingCard';
import { AdminGuard } from '@/components/AdminGuard';
import { QualityTrendChart, EnrichmentTrendChart } from '@/components/charts/QualityTrendChart';
import { useScraperStatus, useScraperHistory, useDataFreshness, useTriggerScrape } from '@/hooks/useProperties';
import { useTranslation } from '@/i18n/LanguageContext';
import { toast } from 'sonner';
import type { EnrichmentPhaseProgress, RefreshStatus, StepResult, DataSourceFreshness, DataWarning, DataQuality, DataQualityStats, GeoEnrichmentStats } from '@/lib/types';

const PHASE_LABELS: Record<string, string> = {
  scraping: 'status.phaseScraping',
  lifecycle_sweep: 'status.phaseLifecycle',
  refreshing_market: 'status.phaseRefreshMarket',
  refreshing_rent: 'status.phaseRefreshRent',
  refreshing_demographics: 'status.phaseRefreshDemographics',
  refreshing_neighbourhood: 'status.phaseRefreshNeighbourhood',
  checking_alerts: 'status.phaseCheckingAlerts',
  enriching_details: 'status.phaseEnrichDetails',
  enriching_walk_scores: 'status.phaseEnrichWalkScores',
  enriching_photos: 'status.phaseEnrichPhotos',
  enriching_conditions: 'status.phaseEnrichConditions',
};

function getFreshnessVariant(ageHours: number | null, thresholdHours: number): 'default' | 'secondary' | 'destructive' {
  if (ageHours === null) return 'destructive';
  if (ageHours <= thresholdHours) return 'default';
  if (ageHours <= thresholdHours * 2) return 'secondary';
  return 'destructive';
}

function getFreshnessLabel(ageHours: number | null, thresholdHours: number, t: (key: string) => string): string {
  if (ageHours === null) return t('status.neverFetched');
  if (ageHours <= thresholdHours) return t('status.fresh');
  return t('status.stale');
}

function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return '-';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function formatDateTime(isoString: string | null): string {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleString();
}

function RefreshStatusBadge({ status, t }: { status: RefreshStatus; t: (key: string) => string }) {
  const variants: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    pending: 'outline',
    running: 'secondary',
    skipped: 'outline',
    done: 'default',
    failed: 'destructive',
  };
  return <Badge variant={variants[status.status] || 'outline'}>{t(`status.${status.status}`)}</Badge>;
}

function EnrichmentBar({ label, progress }: { label: string; progress: EnrichmentPhaseProgress }) {
  const pct = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className="text-muted-foreground">
          {progress.phase === 'pending' ? '-' : `${progress.done}/${progress.total}`}
          {progress.failed > 0 && <span className="text-destructive ml-1">({progress.failed} failed)</span>}
        </span>
      </div>
      {progress.phase !== 'pending' && (
        <Progress value={progress.phase === 'done' ? 100 : pct} className="h-1.5" />
      )}
    </div>
  );
}

const INVESTMENT_TYPES = ['DUPLEX', 'TRIPLEX', 'QUADPLEX', 'MULTIPLEX'];

type QualityFilter = 'all' | 'investment' | 'houses';

function DataQualityCard({
  dataQuality,
  qualityFilter,
  onFilterChange,
  t,
}: {
  dataQuality: DataQuality;
  qualityFilter: QualityFilter;
  onFilterChange: (filter: QualityFilter) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {

  // Compute the stats to display based on the selected filter
  const getFilteredStats = (): DataQualityStats => {
    if (qualityFilter === 'all' || !dataQuality.by_type) {
      return dataQuality;
    }
    if (qualityFilter === 'houses') {
      return dataQuality.by_type['HOUSE'] ?? { total: 0, avg_score: 0, high_quality: 0, low_quality: 0, flagged: 0, corrected: 0 };
    }
    // Investment: sum all plex types
    const empty: DataQualityStats = { total: 0, avg_score: 0, high_quality: 0, low_quality: 0, flagged: 0, corrected: 0 };
    let weightedScore = 0;
    for (const type of INVESTMENT_TYPES) {
      const s = dataQuality.by_type[type];
      if (s) {
        empty.total += s.total;
        empty.high_quality += s.high_quality;
        empty.low_quality += s.low_quality;
        empty.flagged += s.flagged;
        empty.corrected += s.corrected;
        weightedScore += s.total * s.avg_score;
      }
    }
    empty.avg_score = empty.total > 0 ? Math.round(weightedScore / empty.total * 10) / 10 : 0;
    return empty;
  };

  const stats = getFilteredStats();
  const hasBreakdown = dataQuality.by_type && Object.keys(dataQuality.by_type).length > 1;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-blue-500" />
              {t('status.dataQuality')}
            </CardTitle>
            <CardDescription>{t('status.dataQualityDesc')}</CardDescription>
          </div>
          {hasBreakdown && (
            <Tabs value={qualityFilter} onValueChange={(v) => onFilterChange(v as QualityFilter)}>
              <TabsList>
                <TabsTrigger value="all">{t('status.qualityAll')}</TabsTrigger>
                <TabsTrigger value="investment">{t('status.qualityInvestment')}</TabsTrigger>
                <TabsTrigger value="houses">{t('status.qualityHouses')}</TabsTrigger>
              </TabsList>
            </Tabs>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {stats.total > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div>
              <p className="text-2xl font-bold">{stats.avg_score}</p>
              <p className="text-xs text-muted-foreground">{t('status.avgScore')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{stats.high_quality}</p>
              <p className="text-xs text-muted-foreground">{t('status.highQuality')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-red-500">{stats.low_quality}</p>
              <p className="text-xs text-muted-foreground">{t('status.lowQuality')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-500">{stats.flagged}</p>
              <p className="text-xs text-muted-foreground">{t('status.flagged')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-500">{stats.corrected}</p>
              <p className="text-xs text-muted-foreground">{t('status.corrected')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.total}</p>
              <p className="text-xs text-muted-foreground">{t('status.totalValidated')}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No data for this category</p>
        )}
      </CardContent>
    </Card>
  );
}

function FreshnessCard({
  label,
  data,
  t,
}: {
  label: string;
  data: DataSourceFreshness;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-lg flex items-center gap-2">
          <Badge variant={getFreshnessVariant(data.age_hours, data.threshold_hours)}>
            {getFreshnessLabel(data.age_hours, data.threshold_hours, t)}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-sm text-muted-foreground space-y-1">
          <p>{data.last_fetched ? formatRelativeTime(data.last_fetched) : t('status.neverFetched')}</p>
          <p className="text-xs">{t('status.threshold', { hours: data.threshold_hours })}</p>
          {data.total_active !== undefined && (
            <p className="text-xs font-medium">{t('status.totalActive', { count: data.total_active })}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function StatusPage() {
  return (
    <AdminGuard>
      <StatusContent />
    </AdminGuard>
  );
}

function StatusContent() {
  const { t } = useTranslation();
  const { data: status, isLoading: statusLoading } = useScraperStatus();
  const { data: history } = useScraperHistory(30);
  const { data: freshness } = useDataFreshness();
  const triggerMutation = useTriggerScrape();
  const [qualityFilter, setQualityFilter] = useState<QualityFilter>('all');

  const handleTrigger = async () => {
    try {
      await triggerMutation.mutateAsync();
      toast.success(t('status.triggerSuccess'));
    } catch {
      toast.error(t('status.triggerFailed'));
    }
  };

  if (statusLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{t('status.title')}</h1>
          <p className="text-muted-foreground">{t('status.subtitle')}</p>
        </div>
        <LoadingCard message={t('status.loading')} />
      </div>
    );
  }

  if (status?.enabled === false) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{t('status.title')}</h1>
          <p className="text-muted-foreground">{t('status.subtitle')}</p>
        </div>
        <Card>
          <CardContent className="py-6">
            <p className="text-muted-foreground">{t('status.disabled')}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isRunning = status?.is_running ?? false;
  const scrapeProgress = status?.total_steps
    ? Math.round((status.current_step / status.total_steps) * 100)
    : 0;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('status.title')}</h1>
          <p className="text-muted-foreground">{t('status.subtitle')}</p>
        </div>
        <Button
          onClick={handleTrigger}
          disabled={isRunning || triggerMutation.isPending}
        >
          {triggerMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Play className="h-4 w-4 mr-2" />
          )}
          {triggerMutation.isPending ? t('status.triggering') : t('status.triggerScrape')}
        </Button>
      </div>

      {/* Live Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            {t('status.liveStatus')}
            <Badge variant={isRunning ? 'default' : 'secondary'}>
              {isRunning ? t('status.running') : t('status.idle')}
            </Badge>
          </CardTitle>
          {status?.current_phase && (
            <CardDescription className="flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin" />
              {t(PHASE_LABELS[status.current_phase] || status.current_phase)}
              {status.current_phase === 'scraping' && status.current_region && (
                <span className="ml-2">
                  <Badge variant="outline">{status.current_region}</Badge>
                  {' '}
                  <Badge variant="outline">{status.current_type}</Badge>
                </span>
              )}
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Scrape progress bar */}
          {isRunning && status?.current_phase === 'scraping' && (
            <div className="space-y-1">
              <div className="flex justify-between text-sm text-muted-foreground">
                <span>{t('status.phaseScraping')}</span>
                <span>{t('status.progress', { current: status.current_step, total: status.total_steps })}</span>
              </div>
              <Progress value={scrapeProgress} className="h-2" />
            </div>
          )}

          {/* Summary stats */}
          <div className="grid gap-4 sm:grid-cols-3 text-sm">
            <div>
              <span className="text-muted-foreground">{t('status.lastRun', { time: '' })}</span>
              <p className="font-medium">{formatRelativeTime(status?.last_run_completed ?? null)}</p>
            </div>
            <div>
              <span className="text-muted-foreground">{t('status.jobDuration')}</span>
              <p className="font-medium">
                {status?.last_run_duration_sec != null
                  ? t('status.duration', { seconds: status.last_run_duration_sec })
                  : '-'}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">{t('status.nextRun', { time: '' })}</span>
              <p className="font-medium">{formatRelativeTime(status?.next_run_at ?? null)}</p>
            </div>
          </div>

          {/* Enrichment progress */}
          {status?.enrichment_progress && (
            <>
              <Separator />
              <div>
                <h4 className="text-sm font-medium mb-3">{t('status.enrichmentProgress')}</h4>
                <div className="grid gap-3 sm:grid-cols-2">
                  <EnrichmentBar label={t('status.details')} progress={status.enrichment_progress.details} />
                  <EnrichmentBar label={t('status.walkScores')} progress={status.enrichment_progress.walk_scores} />
                  <EnrichmentBar label={t('status.photos')} progress={status.enrichment_progress.photos} />
                  <EnrichmentBar label={t('status.conditions')} progress={status.enrichment_progress.conditions} />
                  {status.enrichment_progress.geo_enrichment && (
                    <EnrichmentBar label={t('status.geoEnrichment')} progress={status.enrichment_progress.geo_enrichment} />
                  )}
                </div>
              </div>
            </>
          )}

          {/* Data refresh statuses */}
          {status?.refresh_progress && (
            <>
              <Separator />
              <div>
                <h4 className="text-sm font-medium mb-3">{t('status.dataRefreshes')}</h4>
                <div className="flex flex-wrap gap-3">
                  <div className="flex items-center gap-2 text-sm">
                    <span>{t('status.marketData')}</span>
                    <RefreshStatusBadge status={status.refresh_progress.market} t={t} />
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span>{t('status.rentData')}</span>
                    <RefreshStatusBadge status={status.refresh_progress.rent} t={t} />
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span>{t('status.demographics')}</span>
                    <RefreshStatusBadge status={status.refresh_progress.demographics} t={t} />
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span>{t('status.neighbourhood')}</span>
                    <RefreshStatusBadge status={status.refresh_progress.neighbourhood} t={t} />
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Errors */}
          {status?.errors && status.errors.length > 0 && (
            <>
              <Separator />
              <div>
                <h4 className="text-sm font-medium mb-2 text-destructive flex items-center gap-1">
                  <AlertTriangle className="h-4 w-4" />
                  {t('status.errors', { count: status.errors.length })}
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1">
                  {status.errors.slice(0, 10).map((err, i) => (
                    <li key={i} className="font-mono text-xs">{err}</li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Data Freshness */}
      {freshness && (
        <Card>
          <CardHeader>
            <CardTitle>{t('status.dataFreshness')}</CardTitle>
            <CardDescription>{t('status.dataFreshnessDesc')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <FreshnessCard label={t('status.listingsData')} data={freshness.listings} t={t} />
              <FreshnessCard label={t('status.marketData')} data={freshness.market_data} t={t} />
              <FreshnessCard label={t('status.rentData')} data={freshness.rent_data} t={t} />
              <FreshnessCard label={t('status.demographics')} data={freshness.demographics} t={t} />
              <FreshnessCard label={t('status.neighbourhood')} data={freshness.neighbourhood} t={t} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Data Quality Summary */}
      {status?.data_quality && status.data_quality.total > 0 && (
        <DataQualityCard dataQuality={status.data_quality} qualityFilter={qualityFilter} onFilterChange={setQualityFilter} t={t} />
      )}

      {/* Geo Enrichment Stats */}
      {status?.geo_stats && status.geo_stats.total_houses > 0 && (() => {
        const g = status.geo_stats as GeoEnrichmentStats;
        const enrichedPct = g.with_coords > 0 ? Math.round(g.enriched / g.with_coords * 100) : 0;
        return (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-emerald-500" />
                {t('status.geoEnrichment')}
              </CardTitle>
              <CardDescription>{t('status.geoEnrichmentDesc')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Overall progress */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1.5">
                  <span className="text-muted-foreground">{t('status.geoOverall')}</span>
                  <span className="font-medium tabular-nums">{g.enriched} / {g.with_coords} ({enrichedPct}%)</span>
                </div>
                <Progress value={enrichedPct} className="h-2" />
              </div>

              {/* Stat grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <p className="text-2xl font-bold">{g.total_houses}</p>
                  <p className="text-xs text-muted-foreground">{t('status.geoTotalHouses')}</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-green-600">{g.enriched}</p>
                  <p className="text-xs text-muted-foreground">{t('status.geoEnriched')}</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-amber-500">{g.pending}</p>
                  <p className="text-xs text-muted-foreground">{t('status.geoPending')}</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-500">{g.incomplete}</p>
                  <p className="text-xs text-muted-foreground">{t('status.geoIncomplete')}</p>
                </div>
              </div>

              {/* Per-source breakdown */}
              <div className="rounded-lg border p-3 space-y-2">
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{t('status.geoSources')}</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div className="flex items-center justify-between text-sm">
                    <span>{t('status.geoSchools')}</span>
                    <span className="font-medium tabular-nums">{g.has_schools}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span>{t('status.geoParks')}</span>
                    <span className="font-medium tabular-nums">{g.has_parks}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span>{t('status.geoFlood')}</span>
                    <span className="font-medium tabular-nums">{g.has_flood}</span>
                  </div>
                </div>
              </div>

              {/* Warnings */}
              {g.no_coords > 0 && (
                <div className="rounded-md border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 px-3 py-2 space-y-1">
                  <p className="text-xs text-amber-700 dark:text-amber-400">
                    {t('status.geoNoCoords', { count: String(g.no_coords) })}
                  </p>
                  {g.geocoding_failed > 0 && (
                    <p className="text-xs text-amber-600 dark:text-amber-500">
                      {t('status.geoGeocodingFailed', { count: String(g.geocoding_failed) })}
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })()}

      {/* Quality Score Trend */}
      {history?.jobs && (
        <Card>
          <CardHeader>
            <CardTitle>{t('status.qualityTrend')}</CardTitle>
            <CardDescription>{t('status.qualityTrendDesc')}</CardDescription>
          </CardHeader>
          <CardContent>
            <QualityTrendChart jobs={history.jobs} qualityFilter={qualityFilter} />
          </CardContent>
        </Card>
      )}

      {/* Enrichment Success Rate Trend */}
      {history?.jobs && (
        <Card>
          <CardHeader>
            <CardTitle>{t('status.enrichmentTrend')}</CardTitle>
            <CardDescription>{t('status.enrichmentTrendDesc')}</CardDescription>
          </CardHeader>
          <CardContent>
            <EnrichmentTrendChart jobs={history.jobs} />
          </CardContent>
        </Card>
      )}

      {/* Data Staleness Warnings */}
      {status?.data_warnings && status.data_warnings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-5 w-5" />
              {t('status.dataWarnings')}
            </CardTitle>
            <CardDescription>{t('status.dataWarningsDesc')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {status.data_warnings.map((w: DataWarning, i: number) => (
                <div key={i} className="rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-3">
                  <p className="text-sm font-medium">{w.source}</p>
                  <p className="text-sm text-muted-foreground">{w.message}</p>
                  <p className="text-xs text-muted-foreground mt-1 font-mono">{w.action}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Run Breakdown */}
      {status?.step_results && status.step_results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>
              {isRunning ? t('status.currentRun') : t('status.lastRunBreakdown')}
            </CardTitle>
            <CardDescription>
              {t('status.listings', { count: status.total_listings_stored })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('status.stepRegion')}</TableHead>
                  <TableHead>{t('status.stepType')}</TableHead>
                  <TableHead className="text-right">{t('status.stepCount')}</TableHead>
                  <TableHead className="text-right">{t('status.stepDuration')}</TableHead>
                  <TableHead className="text-center">{t('status.stepStatus')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {status.step_results.map((step: StepResult, i: number) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{step.region}</TableCell>
                    <TableCell>{step.type}</TableCell>
                    <TableCell className="text-right">{step.count}</TableCell>
                    <TableCell className="text-right">{t('status.duration', { seconds: step.duration_sec })}</TableCell>
                    <TableCell className="text-center">
                      {step.error ? (
                        <XCircle className="h-4 w-4 text-destructive inline" />
                      ) : (
                        <CheckCircle2 className="h-4 w-4 text-primary inline" />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Job History */}
      <Card>
        <CardHeader>
          <CardTitle>{t('status.jobHistory')}</CardTitle>
          <CardDescription>{t('status.jobHistoryDesc')}</CardDescription>
        </CardHeader>
        <CardContent>
          {history && history.jobs.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('status.jobStarted')}</TableHead>
                  <TableHead>{t('status.jobDuration')}</TableHead>
                  <TableHead>{t('status.jobStatus')}</TableHead>
                  <TableHead className="text-right">{t('status.jobListings')}</TableHead>
                  <TableHead className="text-right">{t('status.jobEnriched')}</TableHead>
                  <TableHead className="text-right">{t('status.jobErrors')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="text-sm">{formatDateTime(job.started_at)}</TableCell>
                    <TableCell>
                      {job.duration_sec != null ? t('status.duration', { seconds: job.duration_sec }) : '-'}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          job.status === 'completed' ? 'default' :
                          job.status === 'failed' ? 'destructive' : 'secondary'
                        }
                      >
                        {t(`status.${job.status}`)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{job.total_listings}</TableCell>
                    <TableCell className="text-right">{job.total_enriched}</TableCell>
                    <TableCell className="text-right">
                      {job.errors.length > 0 ? (
                        <span className="text-destructive">{job.errors.length}</span>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8">
              <Clock className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
              <p className="font-medium">{t('status.noHistory')}</p>
              <p className="text-sm text-muted-foreground">{t('status.noHistoryDesc')}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
