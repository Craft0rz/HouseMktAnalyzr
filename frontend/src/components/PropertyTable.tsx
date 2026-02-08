'use client';

import { useState } from 'react';
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { ArrowUpDown, ExternalLink, Plus, Check, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
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
import type { PropertyWithMetrics } from '@/lib/types';

interface PropertyTableProps {
  data: PropertyWithMetrics[];
  onRowClick?: (property: PropertyWithMetrics) => void;
  isLoading?: boolean;
  showCompareColumn?: boolean;
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
  return `${value.toFixed(1)}%`;
};

const formatCashFlow = (value: number | null | undefined) => {
  if (value == null) return '-';
  const formatted = new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(Math.abs(value));
  return value >= 0 ? formatted : `-${formatted}`;
};

const getScoreColor = (score: number) => {
  if (score >= 70) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
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

export function PropertyTable({ data, onRowClick, isLoading, showCompareColumn = true }: PropertyTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'metrics_score', desc: true },
  ]);
  const { addProperty, removeProperty, isSelected, canAdd } = useComparison();

  const handleCompareToggle = (e: React.MouseEvent, property: PropertyWithMetrics) => {
    e.stopPropagation();
    if (isSelected(property.listing.id)) {
      removeProperty(property.listing.id);
    } else if (canAdd) {
      addProperty(property);
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
            title={selected ? 'Remove from comparison' : 'Add to comparison'}
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
          Score
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
                  <span className="text-muted-foreground">Financial</span>
                  <span className="font-medium tabular-nums">{fin.toFixed(0)}/70</span>
                </div>
                <div className="mt-1 h-1 w-full rounded-full bg-muted overflow-hidden">
                  <div className="h-full rounded-full bg-green-500" style={{ width: `${Math.min(100, (fin / 70) * 100)}%` }} />
                </div>
                {loc > 0 && (
                  <>
                    <div className="flex justify-between mt-1.5">
                      <span className="text-muted-foreground">Location</span>
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
      header: 'Address',
      cell: ({ row }) => (
        <div className="max-w-[200px]">
          <div className="font-medium truncate">{row.original.listing.address}</div>
          <div className="text-sm text-muted-foreground">{row.original.listing.city}</div>
        </div>
      ),
    },
    {
      accessorKey: 'listing.property_type',
      header: 'Type',
      cell: ({ row }) => (
        <Badge variant="outline">
          {getPropertyTypeLabel(row.original.listing.property_type)}
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
          Price
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => formatPrice(row.original.listing.price),
    },
    {
      accessorKey: 'listing.units',
      header: 'Units',
      cell: ({ row }) => row.original.listing.units,
    },
    {
      accessorKey: 'metrics.cap_rate',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Cap Rate
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
          Cash Flow
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
      header: 'Yield',
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
          $/Unit
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => formatPrice(row.original.metrics.price_per_unit),
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
    data,
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
        <div className="text-muted-foreground">Loading properties...</div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">No properties found. Try adjusting your search filters.</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border overflow-x-auto">
        <Table className="min-w-[900px]">
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
