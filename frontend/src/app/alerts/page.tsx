'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { AuthGuard } from '@/components/AuthGuard';
import {
  Bell,
  Plus,
  Trash2,
  Power,
  PowerOff,
  Mail,
  MapPin,
  Home,
  DollarSign,
  TrendingUp,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { LoadingCard } from '@/components/LoadingCard';
import {
  useAlerts,
  useCreateAlert,
  useToggleAlert,
  useDeleteAlert,
} from '@/hooks/useProperties';
import { formatPrice } from '@/lib/formatters';
import { useTranslation } from '@/i18n/LanguageContext';
import type { AlertCriteria, CreateAlertRequest } from '@/lib/types';

function AlertCard({
  alert,
  onToggle,
  onDelete,
}: {
  alert: AlertCriteria;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const { t, locale } = useTranslation();

  const regionKeyMap: Record<string, string> = {
    montreal: 'regions.montreal',
    laval: 'regions.laval',
    'south-shore': 'regions.southShore',
    'north-shore': 'regions.northShore',
    laurentides: 'regions.laurentides',
    lanaudiere: 'regions.lanaudiere',
  };

  return (
    <Card className={!alert.enabled ? 'opacity-60' : ''}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`p-2 rounded-full ${
                alert.enabled ? 'bg-green-100 text-green-600' : 'bg-muted text-muted-foreground'
              }`}
            >
              <Bell className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-lg">{alert.name}</CardTitle>
              <CardDescription className="flex items-center gap-2 mt-1">
                {alert.enabled ? (
                  <Badge variant="default" className="text-xs">{t('common.active')}</Badge>
                ) : (
                  <Badge variant="secondary" className="text-xs">{t('common.paused')}</Badge>
                )}
                {alert.last_match_count > 0 && (
                  <span className="text-xs">
                    {t('alerts.matchesFound', { count: alert.last_match_count })}
                  </span>
                )}
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggle}
              title={alert.enabled ? t('alerts.pauseAlert') : t('alerts.enableAlert')}
              aria-label={alert.enabled ? t('alerts.pauseAlert') : t('alerts.enableAlert')}
            >
              {alert.enabled ? (
                <Power className="h-4 w-4 text-green-600" />
              ) : (
                <PowerOff className="h-4 w-4 text-muted-foreground" />
              )}
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="ghost" size="icon" title={t('alerts.deleteAlert')} aria-label={t('alerts.deleteAlert')}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('alerts.deleteAlert')}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {t('alerts.deleteConfirm', { name: alert.name })}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                  <AlertDialogAction onClick={onDelete} className="bg-destructive text-destructive-foreground">
                    {t('common.delete')}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Quick criteria summary */}
        <div className="flex flex-wrap gap-2 mb-3">
          {alert.regions.length > 0 && (
            <Badge variant="outline" className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {alert.regions.length === 1
                ? t(regionKeyMap[alert.regions[0]] ?? '') || alert.regions[0]
                : t('alerts.regionsCount', { count: alert.regions.length })}
            </Badge>
          )}
          {alert.property_types.length > 0 && (
            <Badge variant="outline" className="flex items-center gap-1">
              <Home className="h-3 w-3" />
              {alert.property_types.length === 1
                ? alert.property_types[0]
                : t('alerts.typesCount', { count: alert.property_types.length })}
            </Badge>
          )}
          {(alert.min_price || alert.max_price) && (
            <Badge variant="outline" className="flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              {alert.min_price && alert.max_price
                ? `${formatPrice(alert.min_price, locale)} - ${formatPrice(alert.max_price, locale)}`
                : alert.min_price
                ? `≥ ${formatPrice(alert.min_price, locale)}`
                : `≤ ${formatPrice(alert.max_price!, locale)}`}
            </Badge>
          )}
          {alert.min_score && (
            <Badge variant="outline" className="flex items-center gap-1">
              <TrendingUp className="h-3 w-3" />
              {t('alerts.scoreMin', { score: alert.min_score })}
            </Badge>
          )}
          {alert.notify_email && (
            <Badge variant="outline" className="flex items-center gap-1">
              <Mail className="h-3 w-3" />
              {t('common.email')}
            </Badge>
          )}
        </div>

        {/* Expand/collapse for more details */}
        <Button
          variant="ghost"
          size="sm"
          className="w-full"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <>
              <ChevronUp className="h-4 w-4 mr-2" /> {t('alerts.hideDetails')}
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4 mr-2" /> {t('alerts.showDetails')}
            </>
          )}
        </Button>

        {expanded && (
          <div className="mt-4 space-y-3 text-sm">
            <Separator />
            <div className="grid grid-cols-2 gap-4">
              {alert.min_cap_rate && (
                <div>
                  <span className="text-muted-foreground">{t('alerts.minCapRate')}</span>{' '}
                  <span className="font-medium">{alert.min_cap_rate}%</span>
                </div>
              )}
              {alert.min_cash_flow && (
                <div>
                  <span className="text-muted-foreground">{t('alerts.minCashFlow')}</span>{' '}
                  <span className="font-medium">{formatPrice(alert.min_cash_flow, locale)}/mo</span>
                </div>
              )}
              {alert.max_price_per_unit && (
                <div>
                  <span className="text-muted-foreground">{t('alerts.maxPricePerUnit')}</span>{' '}
                  <span className="font-medium">{formatPrice(alert.max_price_per_unit, locale)}</span>
                </div>
              )}
              {alert.min_yield && (
                <div>
                  <span className="text-muted-foreground">{t('alerts.minYield')}</span>{' '}
                  <span className="font-medium">{alert.min_yield}%</span>
                </div>
              )}
            </div>
            <Separator />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{t('common.created') + ': ' + new Date(alert.created_at).toLocaleDateString()}</span>
              {alert.last_checked && (
                <span>{t('alerts.lastChecked', { date: new Date(alert.last_checked).toLocaleDateString() })}</span>
              )}
            </div>
            <div className="flex gap-4 text-xs">
              <span className={alert.notify_on_new ? 'text-green-600' : 'text-muted-foreground'}>
                {alert.notify_on_new ? '✓' : '✗'} {t('alerts.newListings')}
              </span>
              <span className={alert.notify_on_price_drop ? 'text-green-600' : 'text-muted-foreground'}>
                {alert.notify_on_price_drop ? '✓' : '✗'} {t('alerts.priceDrops')}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CreateAlertDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [selectedRegions, setSelectedRegions] = useState<string[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [minScore, setMinScore] = useState('');
  const [minCapRate, setMinCapRate] = useState('');
  const [minCashFlow, setMinCashFlow] = useState('');
  const [maxPricePerUnit, setMaxPricePerUnit] = useState('');
  const [notifyEmail, setNotifyEmail] = useState('');
  const [notifyOnNew, setNotifyOnNew] = useState(true);
  const [notifyOnPriceDrop, setNotifyOnPriceDrop] = useState(true);

  const { t } = useTranslation();
  const createAlert = useCreateAlert();

  const REGIONS = [
    { value: 'montreal', label: t('regions.montreal') },
    { value: 'laval', label: t('regions.laval') },
    { value: 'south-shore', label: t('regions.southShore') },
    { value: 'north-shore', label: t('regions.northShore') },
    { value: 'laurentides', label: t('regions.laurentides') },
    { value: 'lanaudiere', label: t('regions.lanaudiere') },
  ];

  const PROPERTY_TYPES = [
    { value: 'DUPLEX', label: t('propertyTypes.DUPLEX') },
    { value: 'TRIPLEX', label: t('propertyTypes.TRIPLEX') },
    { value: 'ALL_PLEX', label: t('propertyTypes.ALL_PLEX') },
    { value: 'HOUSE', label: t('propertyTypes.HOUSE') },
  ];

  const toggleRegion = (region: string) => {
    setSelectedRegions((prev) =>
      prev.includes(region) ? prev.filter((r) => r !== region) : [...prev, region]
    );
  };

  const toggleType = (type: string) => {
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const handleSubmit = async () => {
    const data: CreateAlertRequest = {
      name: name || 'New Alert',
      regions: selectedRegions.length > 0 ? selectedRegions : undefined,
      property_types: selectedTypes.length > 0 ? selectedTypes : undefined,
      min_price: minPrice ? parseInt(minPrice) : undefined,
      max_price: maxPrice ? parseInt(maxPrice) : undefined,
      min_score: minScore ? parseInt(minScore) : undefined,
      min_cap_rate: minCapRate ? parseFloat(minCapRate) : undefined,
      min_cash_flow: minCashFlow ? parseInt(minCashFlow) : undefined,
      max_price_per_unit: maxPricePerUnit ? parseInt(maxPricePerUnit) : undefined,
      notify_email: notifyEmail || undefined,
      notify_on_new: notifyOnNew,
      notify_on_price_drop: notifyOnPriceDrop,
    };

    try {
      await createAlert.mutateAsync(data);
      toast.success(t('alerts.alertCreated'));
      setOpen(false);
      resetForm();
      onCreated();
    } catch {
      toast.error(t('alerts.alertCreateFailed'));
    }
  };

  const resetForm = () => {
    setName('');
    setSelectedRegions([]);
    setSelectedTypes([]);
    setMinPrice('');
    setMaxPrice('');
    setMinScore('');
    setMinCapRate('');
    setMinCashFlow('');
    setMaxPricePerUnit('');
    setNotifyEmail('');
    setNotifyOnNew(true);
    setNotifyOnPriceDrop(true);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          {t('alerts.createAlert')}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('alerts.createNew')}</DialogTitle>
          <DialogDescription>
            {t('alerts.createNewDesc')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Alert Name */}
          <div className="space-y-2">
            <label htmlFor="alert-name" className="text-sm font-medium">{t('alerts.alertName')}</label>
            <Input
              id="alert-name"
              placeholder={t('alerts.alertNamePlaceholder')}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {/* Regions */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">{t('alerts.regions')}</legend>
            <div className="flex flex-wrap gap-2">
              {REGIONS.map((region) => (
                <Badge
                  key={region.value}
                  variant={selectedRegions.includes(region.value) ? 'default' : 'outline'}
                  className="cursor-pointer"
                  onClick={() => toggleRegion(region.value)}
                  role="checkbox"
                  aria-checked={selectedRegions.includes(region.value)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && toggleRegion(region.value)}
                >
                  {region.label}
                </Badge>
              ))}
            </div>
          </fieldset>

          {/* Property Types */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">{t('filters.propertyTypes')}</legend>
            <div className="flex flex-wrap gap-2">
              {PROPERTY_TYPES.map((type) => (
                <Badge
                  key={type.value}
                  variant={selectedTypes.includes(type.value) ? 'default' : 'outline'}
                  className="cursor-pointer"
                  onClick={() => toggleType(type.value)}
                  role="checkbox"
                  aria-checked={selectedTypes.includes(type.value)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && toggleType(type.value)}
                >
                  {type.label}
                </Badge>
              ))}
            </div>
          </fieldset>

          {/* Price Range */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">{t('alerts.priceRange')}</legend>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="min-price" className="sr-only">Minimum price</label>
                <Input
                  id="min-price"
                  type="number"
                  step="10000"
                  placeholder={t('alerts.minPricePlaceholder')}
                  value={minPrice}
                  onChange={(e) => setMinPrice(e.target.value)}
                  min="0"
                />
              </div>
              <div>
                <label htmlFor="max-price" className="sr-only">Maximum price</label>
                <Input
                  id="max-price"
                  type="number"
                  step="10000"
                  placeholder={t('alerts.maxPricePlaceholder')}
                  value={maxPrice}
                  onChange={(e) => setMaxPrice(e.target.value)}
                  min="0"
                />
              </div>
            </div>
          </fieldset>

          {/* Investment Criteria */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">{t('alerts.investmentCriteria')}</legend>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label htmlFor="min-score" className="text-xs text-muted-foreground">{t('alerts.minScore')}</label>
                <Input
                  id="min-score"
                  type="number"
                  placeholder="e.g., 70"
                  value={minScore}
                  onChange={(e) => setMinScore(e.target.value)}
                  min="0"
                  max="100"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="min-cap-rate" className="text-xs text-muted-foreground">{t('alerts.minCapRateLabel')}</label>
                <Input
                  id="min-cap-rate"
                  type="number"
                  placeholder="e.g., 5.0"
                  value={minCapRate}
                  onChange={(e) => setMinCapRate(e.target.value)}
                  step="0.1"
                  min="0"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="min-cash-flow" className="text-xs text-muted-foreground">{t('alerts.minCashFlowLabel')}</label>
                <Input
                  id="min-cash-flow"
                  type="number"
                  step="100"
                  placeholder="e.g., 200"
                  value={minCashFlow}
                  onChange={(e) => setMinCashFlow(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="max-price-per-unit" className="text-xs text-muted-foreground">{t('alerts.maxPricePerUnitLabel')}</label>
                <Input
                  id="max-price-per-unit"
                  type="number"
                  step="10000"
                  placeholder="e.g., 200000"
                  value={maxPricePerUnit}
                  onChange={(e) => setMaxPricePerUnit(e.target.value)}
                  min="0"
                />
              </div>
            </div>
          </fieldset>

          <Separator />

          {/* Notification Settings */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-medium">{t('alerts.notifications')}</legend>
            <div className="space-y-2">
              <label htmlFor="notify-email" className="text-xs text-muted-foreground">{t('alerts.emailOptional')}</label>
              <Input
                id="notify-email"
                type="email"
                placeholder="your@email.com"
                value={notifyEmail}
                onChange={(e) => setNotifyEmail(e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between">
              <label htmlFor="notify-new" className="text-sm">{t('alerts.notifyNewListings')}</label>
              <Switch id="notify-new" checked={notifyOnNew} onCheckedChange={setNotifyOnNew} />
            </div>
            <div className="flex items-center justify-between">
              <label htmlFor="notify-price-drop" className="text-sm">{t('alerts.notifyPriceDrops')}</label>
              <Switch id="notify-price-drop" checked={notifyOnPriceDrop} onCheckedChange={setNotifyOnPriceDrop} />
            </div>
          </fieldset>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleSubmit} disabled={createAlert.isPending}>
            {createAlert.isPending ? t('alerts.creating') : t('alerts.createAlert')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function AlertsPage() {
  const { data: alertsData, isLoading, refetch } = useAlerts();
  const toggleAlert = useToggleAlert();
  const deleteAlert = useDeleteAlert();
  const { t } = useTranslation();

  const handleToggle = async (alertId: string, alertName: string, currentState: boolean) => {
    try {
      await toggleAlert.mutateAsync(alertId);
      toast.success(t('alerts.alertToggled', { name: alertName, state: currentState ? t('common.paused') : t('common.active') }));
    } catch {
      toast.error(t('alerts.alertToggleFailed'));
    }
  };

  const handleDelete = async (alertId: string, alertName: string) => {
    try {
      await deleteAlert.mutateAsync(alertId);
      toast.success(t('alerts.alertDeleted', { name: alertName }));
    } catch {
      toast.error(t('alerts.alertDeleteFailed'));
    }
  };

  return (
    <AuthGuard>
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('alerts.title')}</h1>
          <p className="text-muted-foreground">
            {t('alerts.subtitle')}
          </p>
        </div>
        <CreateAlertDialog onCreated={() => refetch()} />
      </div>

      {isLoading ? (
        <LoadingCard message={t('alerts.loadingAlerts')} />
      ) : alertsData?.alerts && alertsData.alerts.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {alertsData.alerts.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onToggle={() => handleToggle(alert.id, alert.name, alert.enabled)}
              onDelete={() => handleDelete(alert.id, alert.name)}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <Bell className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">{t('alerts.noAlerts')}</h3>
            <p className="text-muted-foreground mb-6">
              {t('alerts.noAlertsDesc')}
            </p>
            <CreateAlertDialog onCreated={() => refetch()} />
          </CardContent>
        </Card>
      )}
    </div>
    </AuthGuard>
  );
}
