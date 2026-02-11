'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { ArrowUpDown, ExternalLink, Plus, Check, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, TrendingDown, TrendingUp, Clock, Heart } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useComparison } from '@/lib/comparison-context';
import { usePortfolioContext } from '@/lib/portfolio-context';
import { propertiesApi } from '@/lib/api';
import { useTranslation } from '@/i18n/LanguageContext';
import { formatPrice, formatCashFlow as formatCashFlowUtil } from '@/lib/formatters';
import type { PropertyWithMetrics, PriceChangeMap, LifecycleMap } from '@/lib/types';

export type StatusFilter = 'all' | 'active' | 'new' | 'stale' | 'delisted' | 'price_drop';

interface PropertyTableProps {
  data: PropertyWithMetrics[];
  onRowClick?: (property: PropertyWithMetrics) => void;
  isLoading?: boolean;
  showCompareColumn?: boolean;
  statusFilter?: StatusFilter;
}

const formatPercent = (value: number | null | undefined) => {
  if (value == null) return '-';
  return `${value.toFixed(1)}%`;
};

const getScoreColor = (score: number) => {
  if (score >= 70) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
};

export function PropertyTable({ data, onRowClick, isLoading, showCompareColumn = true, statusFilter = 'all' }: PropertyTableProps) {
  const { t, locale } = useTranslation();
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'metrics_score', desc: true },
  ]);
  const [priceChanges, setPriceChanges] = useState<PriceChangeMap>({});
  const [lifecycle, setLifecycle] = useState<LifecycleMap>({});
  const { addProperty, removeProperty, isSelected, canAdd } = useComparison();
  const { isInPortfolio, addToWatchList, removeFromWatchList } = usePortfolioContext();
  const formatCashFlow = (value: number | null | undefined) => formatCashFlowUtil(value, locale);

  // Fetch recent price changes and lifecycle data when data loads
  useEffect(() => {
    if (data.length === 0) return;
    propertiesApi.getRecentPriceChanges()
      .then((res) => setPriceChanges(res.changes))
      .catch(() => {});
    propertiesApi.getLifecycle()
      .then((res) => setLifecycle(res.listings))
      .catch(() => {});
  }, [data.length]);

  // Filter data based on status filter
  const filteredData = useMemo(() => {
    if (statusFilter === 'all') return data;
    return data.filter((item) => {
      const lc = lifecycle[item.listing.id];
      const pc = priceChanges[item.listing.id];
      switch (statusFilter) {
        case 'active':
          return !lc || lc.status === 'active';
        case 'new':
          return lc && lc.days_on_market !== null && lc.days_on_market <= 2;
        case 'stale':
          return lc?.status === 'stale';
        case 'delisted':
          return lc?.status === 'delisted';
        case 'price_drop':
          return pc && pc.change < 0;
        default:
          return true;
      }
    });
  }, [data, statusFilter, lifecycle, priceChanges]);

  const handleCompareToggle = (e: React.MouseEvent, property: PropertyWithMetrics) => {
    e.stopPropagation();
    if (isSelected(property.listing.id)) {
      removeProperty(property.listing.id);
    } else if (canAdd) {
      addProperty(property);
    }
  };

  const handlePortfolioToggle = (e: React.MouseEvent, property: PropertyWithMetrics) => {
    e.stopPropagation();
    if (isInPortfolio(property.listing.id)) {
      removeFromWatchList(property.listing.id, property.listing.address);
    } else {
      addToWatchList(property);
    }
  };

  const columns: ColumnDef<PropertyWithMetrics>[] = [
    ...(showCompareColumn ? [{
      id: 'compare',
      header: () => <span className="sr-only">Compare</span>,
      cell: ({ row }: { row: { original: PropertyWithMetrics } }) => {
        const selected = isSelected(row.original.listing.id);
        return (
          <Button
            variant={selected ? 'default' : 'outline'}
            size="sm"
            className="h-8 w-8 p-0"
            onClick={(e) => handleCompareToggle(e, row.original)}
            disabled={!selected && !canAdd}
            title={selected ? t('table.removeFromComparison') : t('table.addToComparison')}
          >
            {selected ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          </Button>
        );
      },
    }] : []),
    {
      accessorKey: 'metrics.score',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          {t('table.score')}
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const score = row.original.metrics.score;
        const bd = row.original.metrics.score_breakdown;
        const fin = bd ? (bd.cap_rate ?? 0) + (bd.cash_flow ?? 0) + (bd.price_per_unit ?? 0) : 0;
        const loc = bd ? (bd.neighbourhood_safety ?? 0) + (bd.neighbourhood_vacancy ?? 0) + (bd.neighbourhood_rent_growth ?? 0) + (bd.neighbourhood_affordability ?? 0) + (bd.condition ?? 0) : 0;
        return (
          <div className="group relative flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${getScoreColor(score)}`}
            />
            <span className="font-medium">{score.toFixed(0)}</span>
            {bd && Object.keys(bd).length > 0 && (
              <div className="invisible group-hover:visible absolute left-0 top-full mt-1 z-50 w-44 rounded-md border bg-popover p-2 text-xs shadow-md">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('score.financial')}</span>
                  <span className="font-medium tabular-nums">{fin.toFixed(0)}/70</span>
                </div>
                <div className="mt-1 h-1 w-full rounded-full bg-muted overflow-hidden">
                  <div className="h-full rounded-full bg-green-500" style={{ width: `${Math.min(100, (fin / 70) * 100)}%` }} />
                </div>
                {loc > 0 && (
                  <>
                    <div className="flex justify-between mt-1.5">
                      <span className="text-muted-foreground">{t('score.location')}</span>
                      <span className="font-medium tabular-nums">{loc.toFixed(0)}/30</span>
                    </div>
                    <div className="mt-1 h-1 w-full rounded-full bg-muted overflow-hidden">
                      <div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.min(100, (loc / 30) * 100)}%` }} />
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'listing.address',
      header: t('table.address'),
      cell: ({ row }) => {
        const lc = lifecycle[row.original.listing.id];
        const isNew = lc && lc.days_on_market !== null && lc.days_on_market <= 2;
        const isStale = lc?.status === 'stale';
        const isDelisted = lc?.status === 'delisted';
        return (
          <div className="max-w-[220px]" title={`MLS ${row.original.listing.id}`}>
            <div className="flex items-center gap-1.5">
              <span className="font-medium truncate">{row.original.listing.address}</span>
              {isNew && (
                <Badge className="text-[9px] px-1 py-0 h-4 bg-blue-500 hover:bg-blue-500">{t('table.new')}</Badge>
              )}
              {isStale && (
                <Badge variant="outline" className="text-[9px] px-1 py-0 h-4 border-yellow-500/50 text-yellow-600">{t('table.stale')}</Badge>
              )}
              {isDelisted && (
                <Badge variant="outline" className="text-[9px] px-1 py-0 h-4 border-gray-400/50 text-gray-500">{t('table.removed')}</Badge>
              )}
            </div>
            <div className="text-sm text-muted-foreground">{row.original.listing.city}</div>
          </div>
        );
      },
    },
    {
      accessorKey: 'listing.property_type',
      header: t('table.type'),
      cell: ({ row }) => (
        <Badge variant="outline">
          {t('propertyTypes.' + row.original.listing.property_type)}
        </Badge>
      ),
    },
    {
      accessorKey: 'listing.price',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          {t('table.price')}
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const pc = priceChanges[row.original.listing.id];
        const isDown = pc && pc.change < 0;
        const isUp = pc && pc.change > 0;
        return (
          <div className="flex items-center gap-1.5">
            <span>{formatPrice(row.original.listing.price, locale)}</span>
            {isDown && (
              <Badge variant="outline" className="text-[10px] px-1 py-0 h-4 border-green-500/50 text-green-600 gap-0.5">
                <TrendingDown className="h-3 w-3" />
                {pc.change_pct}%
              </Badge>
            )}
            {isUp && (
              <Badge variant="outline" className="text-[10px] px-1 py-0 h-4 border-red-500/50 text-red-600 gap-0.5">
                <TrendingUp className="h-3 w-3" />
                +{pc.change_pct}%
              </Badge>
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'listing.units',
      header: t('table.units'),
      cell: ({ row }) => row.original.listing.units,
    },
    {
      id: 'dom',
      accessorFn: (row) => lifecycle[row.listing.id]?.days_on_market ?? 9999,
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          <Clock className="mr-1 h-3.5 w-3.5" />
          {t('table.dom')}
          <ArrowUpDown className="ml-1 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const lc = lifecycle[row.original.listing.id];
        if (!lc || lc.days_on_market === null) return <span className="text-muted-foreground">-</span>;
        const dom = lc.days_on_market;
        const color = dom <= 7 ? 'text-blue-600' : dom <= 30 ? 'text-foreground' : dom <= 60 ? 'text-yellow-600' : 'text-red-600';
        return <span className={`tabular-nums ${color}`}>{dom}d</span>;
      },
    },
    {
      accessorKey: 'metrics.cap_rate',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          {t('table.capRate')}
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => formatPercent(row.original.metrics.cap_rate),
    },
    {
      accessorKey: 'metrics.cash_flow_monthly',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          {t('table.cashFlow')}
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const cf = row.original.metrics.cash_flow_monthly;
        return (
          <span className={cf && cf > 0 ? 'text-green-600' : 'text-red-600'}>
            {formatCashFlow(cf)}/mo
          </span>
        );
      },
    },
    {
      accessorKey: 'metrics.gross_rental_yield',
      header: t('table.yield'),
      cell: ({ row }) => (
        <span>
          {formatPercent(row.original.metrics.gross_rental_yield)}
          {row.original.metrics.rent_source === 'cmhc_estimate' && (
            <span className="text-[9px] text-muted-foreground ml-0.5" title="Based on CMHC zone average">*</span>
          )}
        </span>
      ),
    },
    {
      accessorKey: 'metrics.price_per_unit',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          {t('table.pricePerUnit')}
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => formatPrice(row.original.metrics.price_per_unit, locale),
    },
    {
      id: 'watchlist',
      header: () => <span className="sr-only">{t('table.watchList')}</span>,
      cell: ({ row }: { row: { original: PropertyWithMetrics } }) => {
        const saved = isInPortfolio(row.original.listing.id);
        return (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={(e) => handlePortfolioToggle(e, row.original)}
            title={saved ? t('detail.removeFromWatchList') : t('detail.addToWatchList')}
          >
            <Heart className={`h-4 w-4 ${saved ? 'fill-current text-red-500' : 'text-muted-foreground'}`} />
          </Button>
        );
      },
    },
    {
      id: 'actions',
      cell: ({ row }) => (
        <a
          href={row.original.listing.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="text-muted-foreground hover:text-foreground"
        >
          <ExternalLink className="h-4 w-4" />
        </a>
      ),
    },
  ];

  const table = useReactTable({
    data: filteredData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    state: {
      sorting,
    },
    initialState: {
      pagination: {
        pageSize: 25,
      },
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">{t('table.loadingProperties')}</div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">{t('table.noResults')}</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border overflow-x-auto">
        <Table className="min-w-[1000px]">
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className={`cursor-pointer hover:bg-muted/50 ${isSelected(row.original.listing.id) ? 'bg-muted/30' : ''}`}
                onClick={() => onRowClick?.(row.original)}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {table.getPageCount() > 1 && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>
              {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1}
              -
              {Math.min(
                (table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize,
                table.getFilteredRowModel().rows.length
              )}
              {' '}of {table.getFilteredRowModel().rows.length}
            </span>
            <Select
              value={String(table.getState().pagination.pageSize)}
              onValueChange={(value) => table.setPageSize(Number(value))}
            >
              <SelectTrigger className="h-8 w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[25, 50, 100].map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size} / page
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => table.setPageIndex(0)}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronsLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm px-2">
              Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => table.setPageIndex(table.getPageCount() - 1)}
              disabled={!table.getCanNextPage()}
            >
              <ChevronsRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
