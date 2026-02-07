'use client';

import { useState } from 'react';
import { toast } from 'sonner';
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
import type { AlertCriteria, CreateAlertRequest } from '@/lib/types';

const REGIONS = [
  { value: 'montreal', label: 'Montreal' },
  { value: 'laval', label: 'Laval' },
  { value: 'longueuil', label: 'Longueuil' },
  { value: 'south-shore', label: 'South Shore' },
  { value: 'north-shore', label: 'North Shore' },
  { value: 'laurentides', label: 'Laurentides' },
  { value: 'lanaudiere', label: 'Lanaudière' },
  { value: 'monteregie', label: 'Montérégie' },
];

const PROPERTY_TYPES = [
  { value: 'DUPLEX', label: 'Duplex' },
  { value: 'TRIPLEX', label: 'Triplex' },
  { value: 'ALL_PLEX', label: 'All Plex' },
  { value: 'HOUSE', label: 'House' },
];

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
                  <Badge variant="default" className="text-xs">Active</Badge>
                ) : (
                  <Badge variant="secondary" className="text-xs">Paused</Badge>
                )}
                {alert.last_match_count > 0 && (
                  <span className="text-xs">
                    {alert.last_match_count} matches found
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
              title={alert.enabled ? 'Pause alert' : 'Enable alert'}
              aria-label={alert.enabled ? 'Pause alert' : 'Enable alert'}
            >
              {alert.enabled ? (
                <Power className="h-4 w-4 text-green-600" />
              ) : (
                <PowerOff className="h-4 w-4 text-muted-foreground" />
              )}
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="ghost" size="icon" title="Delete alert" aria-label="Delete alert">
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete Alert</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to delete &quot;{alert.name}&quot;? This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={onDelete} className="bg-destructive text-destructive-foreground">
                    Delete
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
                ? REGIONS.find((r) => r.value === alert.regions[0])?.label || alert.regions[0]
                : `${alert.regions.length} regions`}
            </Badge>
          )}
          {alert.property_types.length > 0 && (
            <Badge variant="outline" className="flex items-center gap-1">
              <Home className="h-3 w-3" />
              {alert.property_types.length === 1
                ? alert.property_types[0]
                : `${alert.property_types.length} types`}
            </Badge>
          )}
          {(alert.min_price || alert.max_price) && (
            <Badge variant="outline" className="flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              {alert.min_price && alert.max_price
                ? `${formatPrice(alert.min_price)} - ${formatPrice(alert.max_price)}`
                : alert.min_price
                ? `≥ ${formatPrice(alert.min_price)}`
                : `≤ ${formatPrice(alert.max_price!)}`}
            </Badge>
          )}
          {alert.min_score && (
            <Badge variant="outline" className="flex items-center gap-1">
              <TrendingUp className="h-3 w-3" />
              Score ≥ {alert.min_score}
            </Badge>
          )}
          {alert.notify_email && (
            <Badge variant="outline" className="flex items-center gap-1">
              <Mail className="h-3 w-3" />
              Email
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
              <ChevronUp className="h-4 w-4 mr-2" /> Hide Details
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4 mr-2" /> Show Details
            </>
          )}
        </Button>

        {expanded && (
          <div className="mt-4 space-y-3 text-sm">
            <Separator />
            <div className="grid grid-cols-2 gap-4">
              {alert.min_cap_rate && (
                <div>
                  <span className="text-muted-foreground">Min Cap Rate:</span>{' '}
                  <span className="font-medium">{alert.min_cap_rate}%</span>
                </div>
              )}
              {alert.min_cash_flow && (
                <div>
                  <span className="text-muted-foreground">Min Cash Flow:</span>{' '}
                  <span className="font-medium">{formatPrice(alert.min_cash_flow)}/mo</span>
                </div>
              )}
              {alert.max_price_per_unit && (
                <div>
                  <span className="text-muted-foreground">Max $/Unit:</span>{' '}
                  <span className="font-medium">{formatPrice(alert.max_price_per_unit)}</span>
                </div>
              )}
              {alert.min_yield && (
                <div>
                  <span className="text-muted-foreground">Min Yield:</span>{' '}
                  <span className="font-medium">{alert.min_yield}%</span>
                </div>
              )}
            </div>
            <Separator />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Created: {new Date(alert.created_at).toLocaleDateString()}</span>
              {alert.last_checked && (
                <span>Last checked: {new Date(alert.last_checked).toLocaleDateString()}</span>
              )}
            </div>
            <div className="flex gap-4 text-xs">
              <span className={alert.notify_on_new ? 'text-green-600' : 'text-muted-foreground'}>
                {alert.notify_on_new ? '✓' : '✗'} New listings
              </span>
              <span className={alert.notify_on_price_drop ? 'text-green-600' : 'text-muted-foreground'}>
                {alert.notify_on_price_drop ? '✓' : '✗'} Price drops
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

  const createAlert = useCreateAlert();

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
      toast.success('Alert created successfully');
      setOpen(false);
      resetForm();
      onCreated();
    } catch {
      toast.error('Failed to create alert');
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
          Create Alert
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create New Alert</DialogTitle>
          <DialogDescription>
            Set up criteria to be notified when matching properties are found.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Alert Name */}
          <div className="space-y-2">
            <label htmlFor="alert-name" className="text-sm font-medium">Alert Name</label>
            <Input
              id="alert-name"
              placeholder="My Investment Alert"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {/* Regions */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Regions</legend>
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
            <legend className="text-sm font-medium">Property Types</legend>
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
            <legend className="text-sm font-medium">Price Range</legend>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="min-price" className="sr-only">Minimum price</label>
                <Input
                  id="min-price"
                  type="number"
                  step="10000"
                  placeholder="Min price"
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
                  placeholder="Max price"
                  value={maxPrice}
                  onChange={(e) => setMaxPrice(e.target.value)}
                  min="0"
                />
              </div>
            </div>
          </fieldset>

          {/* Investment Criteria */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Investment Criteria</legend>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label htmlFor="min-score" className="text-xs text-muted-foreground">Min Score (0-100)</label>
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
                <label htmlFor="min-cap-rate" className="text-xs text-muted-foreground">Min Cap Rate (%)</label>
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
                <label htmlFor="min-cash-flow" className="text-xs text-muted-foreground">Min Cash Flow ($/mo)</label>
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
                <label htmlFor="max-price-per-unit" className="text-xs text-muted-foreground">Max Price/Unit ($)</label>
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
            <legend className="text-sm font-medium">Notifications</legend>
            <div className="space-y-2">
              <label htmlFor="notify-email" className="text-xs text-muted-foreground">Email (optional)</label>
              <Input
                id="notify-email"
                type="email"
                placeholder="your@email.com"
                value={notifyEmail}
                onChange={(e) => setNotifyEmail(e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between">
              <label htmlFor="notify-new" className="text-sm">Notify on new listings</label>
              <Switch id="notify-new" checked={notifyOnNew} onCheckedChange={setNotifyOnNew} />
            </div>
            <div className="flex items-center justify-between">
              <label htmlFor="notify-price-drop" className="text-sm">Notify on price drops</label>
              <Switch id="notify-price-drop" checked={notifyOnPriceDrop} onCheckedChange={setNotifyOnPriceDrop} />
            </div>
          </fieldset>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={createAlert.isPending}>
            {createAlert.isPending ? 'Creating...' : 'Create Alert'}
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

  const handleToggle = async (alertId: string, alertName: string, currentState: boolean) => {
    try {
      await toggleAlert.mutateAsync(alertId);
      toast.success(`Alert "${alertName}" ${currentState ? 'paused' : 'enabled'}`);
    } catch {
      toast.error('Failed to toggle alert');
    }
  };

  const handleDelete = async (alertId: string, alertName: string) => {
    try {
      await deleteAlert.mutateAsync(alertId);
      toast.success(`Alert "${alertName}" deleted`);
    } catch {
      toast.error('Failed to delete alert');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Alerts</h1>
          <p className="text-muted-foreground">
            Get notified when properties matching your criteria are found
          </p>
        </div>
        <CreateAlertDialog onCreated={() => refetch()} />
      </div>

      {isLoading ? (
        <LoadingCard message="Loading alerts..." />
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
            <h3 className="text-lg font-medium mb-2">No alerts yet</h3>
            <p className="text-muted-foreground mb-6">
              Create your first alert to be notified when matching properties are found.
            </p>
            <CreateAlertDialog onCreated={() => refetch()} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
