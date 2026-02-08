'use client';

import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import {
  Bell,
  Briefcase,
  Eye,
  Home,
  Plus,
  Trash2,
  Edit2,
  ArrowUpDown,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  usePortfolio,
  useAddToPortfolio,
  useRemoveFromPortfolio,
  useTogglePortfolioStatus,
} from '@/hooks/useProperties';
import { portfolioApi } from '@/lib/api';
import { formatPrice } from '@/lib/formatters';
import { useTranslation } from '@/i18n/LanguageContext';
import type { PortfolioItem, PortfolioStatus, CreatePortfolioItemRequest, PortfolioNotification } from '@/lib/types';

function PortfolioSummaryCards({ summary }: { summary: {
  total_owned: number;
  total_watching: number;
  total_invested: number;
  total_equity: number;
  monthly_cash_flow: number;
  annual_cash_flow: number;
  avg_return: number;
} }) {
  const { t, locale } = useTranslation();

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>{t('portfolio.totalInvested')}</CardDescription>
          <CardTitle className="text-2xl">{formatPrice(summary.total_invested, locale)}</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>{t('portfolio.monthlyCashFlow')}</CardDescription>
          <CardTitle className={`text-2xl ${summary.monthly_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatPrice(summary.monthly_cash_flow, locale)}
          </CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>{t('portfolio.avgReturn')}</CardDescription>
          <CardTitle className="text-2xl">{summary.avg_return.toFixed(1)}%</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>{t('portfolio.properties')}</CardDescription>
          <CardTitle className="text-2xl">
            {t('portfolio.ownedWatching', { owned: summary.total_owned, watching: summary.total_watching })}
          </CardTitle>
        </CardHeader>
      </Card>
    </div>
  );
}

function PortfolioItemCard({
  item,
  onEdit,
  onDelete,
  onToggleStatus,
}: {
  item: PortfolioItem;
  onEdit: () => void;
  onDelete: () => void;
  onToggleStatus: () => void;
}) {
  const { t, locale } = useTranslation();
  const dateLocale = locale === 'fr' ? 'fr-CA' : 'en-CA';

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`p-2 rounded-full ${
                item.status === 'owned' ? 'bg-green-100 text-green-600' : 'bg-blue-100 text-blue-600'
              }`}
            >
              {item.status === 'owned' ? <Home className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </div>
            <div>
              <CardTitle className="text-lg">{item.address}</CardTitle>
              <CardDescription className="flex items-center gap-2 mt-1">
                <Badge variant="outline">{t(`propertyTypes.${item.property_type}`)}</Badge>
                <Badge variant={item.status === 'owned' ? 'default' : 'secondary'}>
                  {item.status === 'owned' ? t('portfolio.owned') : t('portfolio.watching')}
                </Badge>
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleStatus}
              title={item.status === 'owned' ? t('portfolio.moveToWatching') : t('portfolio.markAsOwned')}
              aria-label={item.status === 'owned' ? t('portfolio.moveToWatching') : t('portfolio.markAsOwned')}
            >
              <ArrowUpDown className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onEdit}
              title={t('portfolio.editProperty')}
              aria-label={t('portfolio.editProperty')}
            >
              <Edit2 className="h-4 w-4" />
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  title={t('portfolio.removeFromPortfolio')}
                  aria-label={t('portfolio.removeFromPortfolio')}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('portfolio.removeFromPortfolio')}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {t('portfolio.removeConfirm', { address: item.address })}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                  <AlertDialogAction onClick={onDelete} className="bg-destructive text-destructive-foreground">
                    {t('portfolio.remove')}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {item.status === 'owned' && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            {item.purchase_price && (
              <div>
                <div className="text-muted-foreground">{t('portfolio.purchasePrice')}</div>
                <div className="font-medium">{formatPrice(item.purchase_price, locale)}</div>
              </div>
            )}
            {item.down_payment && (
              <div>
                <div className="text-muted-foreground">{t('portfolio.downPaymentLabel')}</div>
                <div className="font-medium">{formatPrice(item.down_payment, locale)}</div>
              </div>
            )}
            {item.current_rent && (
              <div>
                <div className="text-muted-foreground">{t('portfolio.monthlyRent')}</div>
                <div className="font-medium">{formatPrice(item.current_rent, locale)}</div>
              </div>
            )}
            {item.monthly_cash_flow != null && (
              <div>
                <div className="text-muted-foreground">{t('portfolio.cashFlow')}</div>
                <div className={`font-medium ${item.monthly_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatPrice(item.monthly_cash_flow, locale)}{t('common.perMonth')}
                </div>
              </div>
            )}
            {item.annual_return != null && (
              <div>
                <div className="text-muted-foreground">{t('portfolio.annualReturn')}</div>
                <div className="font-medium">{item.annual_return.toFixed(1)}%</div>
              </div>
            )}
            {item.purchase_date && (
              <div>
                <div className="text-muted-foreground">{t('portfolio.purchased')}</div>
                <div className="font-medium">{new Date(item.purchase_date).toLocaleDateString(dateLocale)}</div>
              </div>
            )}
          </div>
        )}
        {item.notes && (
          <p className="text-sm text-muted-foreground mt-4 italic">{item.notes}</p>
        )}
      </CardContent>
    </Card>
  );
}

function AddPropertyDialog({ onAdded }: { onAdded: () => void }) {
  const { t, locale } = useTranslation();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<PortfolioStatus>('watching');
  const [address, setAddress] = useState('');
  const [propertyType, setPropertyType] = useState('TRIPLEX');
  const [purchasePrice, setPurchasePrice] = useState('');
  const [purchaseDate, setPurchaseDate] = useState('');
  const [downPayment, setDownPayment] = useState('');
  const [mortgageRate, setMortgageRate] = useState('');
  const [currentRent, setCurrentRent] = useState('');
  const [currentExpenses, setCurrentExpenses] = useState('');
  const [notes, setNotes] = useState('');

  const addToPortfolio = useAddToPortfolio();

  const handleSubmit = async () => {
    const data: CreatePortfolioItemRequest = {
      property_id: `manual-${Date.now()}`,
      status,
      address,
      property_type: propertyType,
      purchase_price: purchasePrice ? parseInt(purchasePrice) : undefined,
      purchase_date: purchaseDate || undefined,
      down_payment: downPayment ? parseInt(downPayment) : undefined,
      mortgage_rate: mortgageRate ? parseFloat(mortgageRate) : undefined,
      current_rent: currentRent ? parseInt(currentRent) : undefined,
      current_expenses: currentExpenses ? parseInt(currentExpenses) : undefined,
      notes: notes || undefined,
    };

    try {
      await addToPortfolio.mutateAsync(data);
      toast.success(t('portfolio.addedSuccess', { address }));
      setOpen(false);
      resetForm();
      onAdded();
    } catch {
      toast.error(t('portfolio.addFailed'));
    }
  };

  const resetForm = () => {
    setStatus('watching');
    setAddress('');
    setPropertyType('TRIPLEX');
    setPurchasePrice('');
    setPurchaseDate('');
    setDownPayment('');
    setMortgageRate('');
    setCurrentRent('');
    setCurrentExpenses('');
    setNotes('');
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          {t('portfolio.addProperty')}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('portfolio.addToPortfolio')}</DialogTitle>
          <DialogDescription>
            {t('portfolio.addToPortfolioDesc')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Status */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">{t('portfolio.status')}</legend>
            <div className="flex gap-2">
              <Badge
                variant={status === 'watching' ? 'default' : 'outline'}
                className="cursor-pointer"
                onClick={() => setStatus('watching')}
                role="radio"
                aria-checked={status === 'watching'}
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && setStatus('watching')}
              >
                <Eye className="h-3 w-3 mr-1" />
                {t('portfolio.watching')}
              </Badge>
              <Badge
                variant={status === 'owned' ? 'default' : 'outline'}
                className="cursor-pointer"
                onClick={() => setStatus('owned')}
                role="radio"
                aria-checked={status === 'owned'}
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && setStatus('owned')}
              >
                <Home className="h-3 w-3 mr-1" />
                {t('portfolio.owned')}
              </Badge>
            </div>
          </fieldset>

          {/* Basic Info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2 space-y-2">
              <label htmlFor="portfolio-address" className="text-sm font-medium">{t('portfolio.address')}</label>
              <Input
                id="portfolio-address"
                placeholder={t('portfolio.addressPlaceholder')}
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="portfolio-type" className="text-sm font-medium">{t('portfolio.propertyType')}</label>
              <select
                id="portfolio-type"
                className="w-full h-10 px-3 rounded-md border border-input bg-background"
                value={propertyType}
                onChange={(e) => setPropertyType(e.target.value)}
              >
                <option value="DUPLEX">{t('propertyTypes.DUPLEX')}</option>
                <option value="TRIPLEX">{t('propertyTypes.TRIPLEX')}</option>
                <option value="QUADPLEX">{t('propertyTypes.QUADPLEX')}</option>
                <option value="MULTIPLEX">{t('propertyTypes.MULTIPLEX')}</option>
                <option value="HOUSE">{t('propertyTypes.HOUSE')}</option>
              </select>
            </div>
          </div>

          {status === 'owned' && (
            <>
              <Separator />
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label htmlFor="purchase-price" className="text-sm font-medium">{t('portfolio.purchasePriceInput')}</label>
                  <Input
                    id="purchase-price"
                    type="number"
                    step="10000"
                    placeholder="500000"
                    value={purchasePrice}
                    onChange={(e) => setPurchasePrice(e.target.value)}
                    min="0"
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="purchase-date" className="text-sm font-medium">{t('portfolio.purchaseDate')}</label>
                  <Input
                    id="purchase-date"
                    type="date"
                    value={purchaseDate}
                    onChange={(e) => setPurchaseDate(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="down-payment" className="text-sm font-medium">{t('portfolio.downPaymentInput')}</label>
                  <Input
                    id="down-payment"
                    type="number"
                    step="5000"
                    placeholder="100000"
                    value={downPayment}
                    onChange={(e) => setDownPayment(e.target.value)}
                    min="0"
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="mortgage-rate" className="text-sm font-medium">{t('portfolio.mortgageRate')}</label>
                  <Input
                    id="mortgage-rate"
                    type="number"
                    placeholder="5.0"
                    step="0.1"
                    value={mortgageRate}
                    onChange={(e) => setMortgageRate(e.target.value)}
                    min="0"
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="current-rent" className="text-sm font-medium">{t('portfolio.monthlyRentInput')}</label>
                  <Input
                    id="current-rent"
                    type="number"
                    step="100"
                    placeholder="3500"
                    value={currentRent}
                    onChange={(e) => setCurrentRent(e.target.value)}
                    min="0"
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="current-expenses" className="text-sm font-medium">{t('portfolio.monthlyExpenses')}</label>
                  <Input
                    id="current-expenses"
                    type="number"
                    step="100"
                    placeholder="1000"
                    value={currentExpenses}
                    onChange={(e) => setCurrentExpenses(e.target.value)}
                    min="0"
                  />
                </div>
              </div>
            </>
          )}

          <div className="space-y-2">
            <label htmlFor="portfolio-notes" className="text-sm font-medium">{t('portfolio.notes')}</label>
            <Input
              id="portfolio-notes"
              placeholder={t('portfolio.notesPlaceholder')}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleSubmit} disabled={!address || addToPortfolio.isPending}>
            {addToPortfolio.isPending ? t('portfolio.adding') : t('portfolio.addButton')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function PortfolioPage() {
  const { t, locale } = useTranslation();
  const dateLocale = locale === 'fr' ? 'fr-CA' : 'en-CA';
  const { data: portfolioData, isLoading, refetch } = usePortfolio();
  const removeFromPortfolio = useRemoveFromPortfolio();
  const toggleStatus = useTogglePortfolioStatus();

  const [editItem, setEditItem] = useState<PortfolioItem | null>(null);
  const [notifications, setNotifications] = useState<PortfolioNotification[]>([]);

  useEffect(() => {
    portfolioApi.getUpdates()
      .then((res) => setNotifications(res.notifications))
      .catch(() => {});
  }, []);

  const ownedItems = portfolioData?.items.filter((i) => i.status === 'owned') || [];
  const watchingItems = portfolioData?.items.filter((i) => i.status === 'watching') || [];

  const handleDelete = async (itemId: string, address: string) => {
    try {
      await removeFromPortfolio.mutateAsync(itemId);
      toast.success(t('portfolio.removedSuccess', { address }));
    } catch {
      toast.error(t('portfolio.removeFailed'));
    }
  };

  const handleToggleStatus = async (itemId: string, currentStatus: PortfolioStatus, address: string) => {
    const newStatus = currentStatus === 'owned' ? t('portfolio.watching').toLowerCase() : t('portfolio.owned').toLowerCase();
    try {
      await toggleStatus.mutateAsync(itemId);
      toast.success(t('portfolio.statusChanged', { address, status: newStatus }));
    } catch {
      toast.error(t('portfolio.statusChangeFailed'));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('portfolio.title')}</h1>
          <p className="text-muted-foreground">
            {t('portfolio.subtitle')}
          </p>
        </div>
        <AddPropertyDialog onAdded={() => refetch()} />
      </div>

      {isLoading ? (
        <LoadingCard message={t('portfolio.loadingPortfolio')} />
      ) : portfolioData && portfolioData.count > 0 ? (
        <>
          {/* Summary Cards */}
          <PortfolioSummaryCards summary={portfolioData.summary} />

          {/* Notifications */}
          {notifications.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Bell className="h-5 w-5 text-primary" />
                  <CardTitle className="text-lg">{t('portfolio.updates')}</CardTitle>
                  <Badge variant="secondary">{notifications.length}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {notifications.map((n, i) => (
                  <div key={`${n.property_id}-${i}`} className="flex items-center gap-3 p-2 rounded-md border text-sm">
                    {n.type === 'price_drop' && <TrendingDown className="h-4 w-4 text-green-600 shrink-0" />}
                    {n.type === 'price_increase' && <TrendingUp className="h-4 w-4 text-red-600 shrink-0" />}
                    {n.type === 'status_change' && <AlertTriangle className="h-4 w-4 text-yellow-600 shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <span className="font-medium truncate">{n.address}</span>
                      {n.type === 'price_drop' && (
                        <span className="text-green-600 ml-2">
                          {t('portfolio.priceDropped', { pct: n.change_pct ?? 0, old: formatPrice(n.old_price ?? 0, locale), new: formatPrice(n.new_price ?? 0, locale) })}
                        </span>
                      )}
                      {n.type === 'price_increase' && (
                        <span className="text-red-600 ml-2">
                          {t('portfolio.priceIncreased', { pct: n.change_pct ?? 0, old: formatPrice(n.old_price ?? 0, locale), new: formatPrice(n.new_price ?? 0, locale) })}
                        </span>
                      )}
                      {n.type === 'status_change' && (
                        <span className="text-yellow-600 ml-2">
                          {t('portfolio.listingStatus', { status: n.listing_status ?? '' })}
                        </span>
                      )}
                    </div>
                    {n.recorded_at && (
                      <span className="text-xs text-muted-foreground shrink-0">
                        {new Date(n.recorded_at).toLocaleDateString(dateLocale)}
                      </span>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Tabs for Owned / Watching */}
          <Tabs defaultValue="owned" className="space-y-4">
            <TabsList>
              <TabsTrigger value="owned" className="flex items-center gap-2">
                <Home className="h-4 w-4" />
                {t('portfolio.owned')} ({ownedItems.length})
              </TabsTrigger>
              <TabsTrigger value="watching" className="flex items-center gap-2">
                <Eye className="h-4 w-4" />
                {t('portfolio.watching')} ({watchingItems.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="owned" className="space-y-4">
              {ownedItems.length > 0 ? (
                ownedItems.map((item) => (
                  <PortfolioItemCard
                    key={item.id}
                    item={item}
                    onEdit={() => setEditItem(item)}
                    onDelete={() => handleDelete(item.id, item.address)}
                    onToggleStatus={() => handleToggleStatus(item.id, item.status, item.address)}
                  />
                ))
              ) : (
                <Card>
                  <CardContent className="py-8 text-center text-muted-foreground">
                    {t('portfolio.noOwnedProperties')}
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="watching" className="space-y-4">
              {watchingItems.length > 0 ? (
                watchingItems.map((item) => (
                  <PortfolioItemCard
                    key={item.id}
                    item={item}
                    onEdit={() => setEditItem(item)}
                    onDelete={() => handleDelete(item.id, item.address)}
                    onToggleStatus={() => handleToggleStatus(item.id, item.status, item.address)}
                  />
                ))
              ) : (
                <Card>
                  <CardContent className="py-8 text-center text-muted-foreground">
                    {t('portfolio.noWatchlistProperties')}
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <Briefcase className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">{t('portfolio.emptyPortfolio')}</h3>
            <p className="text-muted-foreground mb-6">
              {t('portfolio.emptyPortfolioDesc')}
            </p>
            <AddPropertyDialog onAdded={() => refetch()} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
