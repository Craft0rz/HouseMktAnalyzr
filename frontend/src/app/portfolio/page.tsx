'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import {
  Briefcase,
  Eye,
  Home,
  Plus,
  Trash2,
  Edit2,
  ArrowUpDown,
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
import { formatPrice } from '@/lib/formatters';
import type { PortfolioItem, PortfolioStatus, CreatePortfolioItemRequest } from '@/lib/types';

function PortfolioSummaryCards({ summary }: { summary: {
  total_owned: number;
  total_watching: number;
  total_invested: number;
  total_equity: number;
  monthly_cash_flow: number;
  annual_cash_flow: number;
  avg_return: number;
} }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Total Invested</CardDescription>
          <CardTitle className="text-2xl">{formatPrice(summary.total_invested)}</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Monthly Cash Flow</CardDescription>
          <CardTitle className={`text-2xl ${summary.monthly_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatPrice(summary.monthly_cash_flow)}
          </CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Avg Return</CardDescription>
          <CardTitle className="text-2xl">{summary.avg_return.toFixed(1)}%</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Properties</CardDescription>
          <CardTitle className="text-2xl">
            {summary.total_owned} owned / {summary.total_watching} watching
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
                <Badge variant="outline">{item.property_type}</Badge>
                <Badge variant={item.status === 'owned' ? 'default' : 'secondary'}>
                  {item.status === 'owned' ? 'Owned' : 'Watching'}
                </Badge>
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleStatus}
              title={item.status === 'owned' ? 'Move to watching' : 'Mark as owned'}
              aria-label={item.status === 'owned' ? 'Move to watching' : 'Mark as owned'}
            >
              <ArrowUpDown className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onEdit}
              title="Edit property"
              aria-label="Edit property"
            >
              <Edit2 className="h-4 w-4" />
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  title="Remove from portfolio"
                  aria-label="Remove from portfolio"
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Remove from Portfolio</AlertDialogTitle>
                  <AlertDialogDescription>
                    Remove &quot;{item.address}&quot; from your portfolio?
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={onDelete} className="bg-destructive text-destructive-foreground">
                    Remove
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
                <div className="text-muted-foreground">Purchase Price</div>
                <div className="font-medium">{formatPrice(item.purchase_price)}</div>
              </div>
            )}
            {item.down_payment && (
              <div>
                <div className="text-muted-foreground">Down Payment</div>
                <div className="font-medium">{formatPrice(item.down_payment)}</div>
              </div>
            )}
            {item.current_rent && (
              <div>
                <div className="text-muted-foreground">Monthly Rent</div>
                <div className="font-medium">{formatPrice(item.current_rent)}</div>
              </div>
            )}
            {item.monthly_cash_flow != null && (
              <div>
                <div className="text-muted-foreground">Cash Flow</div>
                <div className={`font-medium ${item.monthly_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatPrice(item.monthly_cash_flow)}/mo
                </div>
              </div>
            )}
            {item.annual_return != null && (
              <div>
                <div className="text-muted-foreground">Annual Return</div>
                <div className="font-medium">{item.annual_return.toFixed(1)}%</div>
              </div>
            )}
            {item.purchase_date && (
              <div>
                <div className="text-muted-foreground">Purchased</div>
                <div className="font-medium">{new Date(item.purchase_date).toLocaleDateString()}</div>
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
      toast.success('Property added to portfolio');
      setOpen(false);
      resetForm();
      onAdded();
    } catch {
      toast.error('Failed to add property');
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
          Add Property
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add Property to Portfolio</DialogTitle>
          <DialogDescription>
            Track an owned property or add to your watchlist.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Status */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Status</legend>
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
                Watching
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
                Owned
              </Badge>
            </div>
          </fieldset>

          {/* Basic Info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2 space-y-2">
              <label htmlFor="portfolio-address" className="text-sm font-medium">Address</label>
              <Input
                id="portfolio-address"
                placeholder="123 Main St, Montreal, QC"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="portfolio-type" className="text-sm font-medium">Property Type</label>
              <select
                id="portfolio-type"
                className="w-full h-10 px-3 rounded-md border border-input bg-background"
                value={propertyType}
                onChange={(e) => setPropertyType(e.target.value)}
              >
                <option value="DUPLEX">Duplex</option>
                <option value="TRIPLEX">Triplex</option>
                <option value="QUADPLEX">Quadplex</option>
                <option value="MULTIPLEX">Multiplex</option>
                <option value="HOUSE">House</option>
              </select>
            </div>
          </div>

          {status === 'owned' && (
            <>
              <Separator />
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label htmlFor="purchase-price" className="text-sm font-medium">Purchase Price ($)</label>
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
                  <label htmlFor="purchase-date" className="text-sm font-medium">Purchase Date</label>
                  <Input
                    id="purchase-date"
                    type="date"
                    value={purchaseDate}
                    onChange={(e) => setPurchaseDate(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="down-payment" className="text-sm font-medium">Down Payment ($)</label>
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
                  <label htmlFor="mortgage-rate" className="text-sm font-medium">Mortgage Rate (%)</label>
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
                  <label htmlFor="current-rent" className="text-sm font-medium">Monthly Rent ($)</label>
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
                  <label htmlFor="current-expenses" className="text-sm font-medium">Monthly Expenses ($)</label>
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
            <label htmlFor="portfolio-notes" className="text-sm font-medium">Notes (optional)</label>
            <Input
              id="portfolio-notes"
              placeholder="Any notes about this property..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!address || addToPortfolio.isPending}>
            {addToPortfolio.isPending ? 'Adding...' : 'Add to Portfolio'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function PortfolioPage() {
  const { data: portfolioData, isLoading, refetch } = usePortfolio();
  const removeFromPortfolio = useRemoveFromPortfolio();
  const toggleStatus = useTogglePortfolioStatus();

  const [editItem, setEditItem] = useState<PortfolioItem | null>(null);

  const ownedItems = portfolioData?.items.filter((i) => i.status === 'owned') || [];
  const watchingItems = portfolioData?.items.filter((i) => i.status === 'watching') || [];

  const handleDelete = async (itemId: string, address: string) => {
    try {
      await removeFromPortfolio.mutateAsync(itemId);
      toast.success(`"${address}" removed from portfolio`);
    } catch {
      toast.error('Failed to remove property');
    }
  };

  const handleToggleStatus = async (itemId: string, currentStatus: PortfolioStatus) => {
    try {
      await toggleStatus.mutateAsync(itemId);
      toast.success(`Property moved to ${currentStatus === 'owned' ? 'watching' : 'owned'}`);
    } catch {
      toast.error('Failed to update status');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Portfolio</h1>
          <p className="text-muted-foreground">
            Track your investment properties and monitor performance
          </p>
        </div>
        <AddPropertyDialog onAdded={() => refetch()} />
      </div>

      {isLoading ? (
        <LoadingCard message="Loading portfolio..." />
      ) : portfolioData && portfolioData.count > 0 ? (
        <>
          {/* Summary Cards */}
          <PortfolioSummaryCards summary={portfolioData.summary} />

          {/* Tabs for Owned / Watching */}
          <Tabs defaultValue="owned" className="space-y-4">
            <TabsList>
              <TabsTrigger value="owned" className="flex items-center gap-2">
                <Home className="h-4 w-4" />
                Owned ({ownedItems.length})
              </TabsTrigger>
              <TabsTrigger value="watching" className="flex items-center gap-2">
                <Eye className="h-4 w-4" />
                Watching ({watchingItems.length})
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
                    onToggleStatus={() => handleToggleStatus(item.id, item.status)}
                  />
                ))
              ) : (
                <Card>
                  <CardContent className="py-8 text-center text-muted-foreground">
                    No owned properties yet. Add one or move from watchlist.
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
                    onToggleStatus={() => handleToggleStatus(item.id, item.status)}
                  />
                ))
              ) : (
                <Card>
                  <CardContent className="py-8 text-center text-muted-foreground">
                    No properties in watchlist. Add properties you&apos;re interested in.
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
            <h3 className="text-lg font-medium mb-2">No properties in portfolio</h3>
            <p className="text-muted-foreground mb-6">
              Start tracking your investments by adding properties.
            </p>
            <AddPropertyDialog onAdded={() => refetch()} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
