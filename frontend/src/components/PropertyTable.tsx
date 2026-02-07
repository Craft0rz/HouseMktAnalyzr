'use client';

import { useState } from 'react';
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { ArrowUpDown, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { PropertyWithMetrics } from '@/lib/types';

interface PropertyTableProps {
  data: PropertyWithMetrics[];
  onRowClick?: (property: PropertyWithMetrics) => void;
  isLoading?: boolean;
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

export function PropertyTable({ data, onRowClick, isLoading }: PropertyTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'score', desc: true },
  ]);

  const columns: ColumnDef<PropertyWithMetrics>[] = [
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
        return (
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${getScoreColor(score)}`}
            />
            <span className="font-medium">{score.toFixed(0)}</span>
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
      cell: ({ row }) => formatPercent(row.original.metrics.gross_rental_yield),
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
    onSortingChange: setSorting,
    state: {
      sorting,
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
    <div className="rounded-md border">
      <Table>
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
              className="cursor-pointer hover:bg-muted/50"
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
  );
}
