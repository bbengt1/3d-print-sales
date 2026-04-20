import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Download, Plus } from 'lucide-react';
import api from '@/api/client';
import { cn, formatCurrency } from '@/lib/utils';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column, type SortDir } from '@/components/data/DataTable';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import SearchInput from '@/components/data/SearchInput';
import Select from '@/components/data/Select';
import Pagination from '@/components/data/Pagination';
import { Button } from '@/components/ui/Button';
import type { PaginatedSales, SaleListItem, SalesChannel } from '@/types';

const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'paid', label: 'Paid' },
  { value: 'shipped', label: 'Shipped' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'refunded', label: 'Refunded' },
  { value: 'cancelled', label: 'Cancelled' },
];

const DEFAULT_PAYMENT_METHODS = ['cash', 'card', 'other'];

/** Build a CSV from the selected sale rows. */
function buildSelectedSalesCsv(rows: SaleListItem[]): string {
  const header = [
    'sale_number',
    'date',
    'customer_name',
    'channel_name',
    'payment_method',
    'status',
    'total',
    'gross_profit',
    'contribution_margin',
    'item_count',
  ];
  const escape = (value: string | number | null | undefined) => {
    if (value == null) return '';
    const s = String(value);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    header.join(','),
    ...rows.map((r) =>
      [
        r.sale_number,
        r.date,
        r.customer_name ?? '',
        r.channel_name ?? 'Direct',
        r.payment_method ?? '',
        r.status,
        r.total,
        r.gross_profit,
        r.contribution_margin,
        r.item_count,
      ]
        .map(escape)
        .join(','),
    ),
  ];
  return lines.join('\n');
}

export default function SalesPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [channelId, setChannelId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('');
  const [sortKey, setSortKey] = useState<string>('date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery<PaginatedSales>({
    queryKey: ['sales', search, status, channelId, paymentMethod, sortKey, sortDir, page, pageSize],
    queryFn: () =>
      api
        .get('/sales', {
          params: {
            search: search || undefined,
            status: status || undefined,
            channel_id: channelId || undefined,
            payment_method: paymentMethod || undefined,
            sort_by: sortKey || undefined,
            sort_dir: sortDir,
            skip: page * pageSize,
            limit: pageSize,
          },
        })
        .then((r) => r.data),
  });

  const { data: channels } = useQuery<SalesChannel[]>({
    queryKey: ['sales-channels'],
    queryFn: () => api.get('/sales/channels').then((r) => r.data),
  });

  const sales = data?.items || [];
  const total = data?.total || 0;
  const paymentMethods = Array.from(
    new Set([...DEFAULT_PAYMENT_METHODS, ...sales.map((s) => s.payment_method).filter(Boolean)]),
  ) as string[];

  const activeFilters = [search, status, channelId, paymentMethod].filter(Boolean).length;

  const clearFilters = () => {
    setSearch('');
    setStatus('');
    setChannelId('');
    setPaymentMethod('');
    setPage(0);
  };

  const handleSortChange = (key: string, dir: SortDir | null) => {
    if (!key || !dir) {
      setSortKey('date');
      setSortDir('desc');
    } else {
      setSortKey(key);
      setSortDir(dir);
    }
    setPage(0);
  };

  const exportSelected = () => {
    const chosen = sales.filter((s) => selected.has(s.id));
    if (!chosen.length) return;
    const csv = buildSelectedSalesCsv(chosen);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `sales-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const columns: Column<SaleListItem>[] = [
    {
      key: 'sale_number',
      header: 'Sale #',
      sortable: true,
      cell: (s) => <span className="font-mono text-xs tabular-nums">{s.sale_number}</span>,
    },
    { key: 'date', header: 'Date', sortable: true, cell: (s) => s.date },
    {
      key: 'customer_name',
      header: 'Customer',
      cell: (s) => s.customer_name || <span className="text-muted-foreground">—</span>,
    },
    {
      key: 'channel_name',
      header: 'Channel',
      colClassName: 'hidden lg:table-cell',
      cell: (s) => s.channel_name || 'Direct',
    },
    {
      key: 'payment_method',
      header: 'Payment',
      sortable: true,
      colClassName: 'hidden lg:table-cell',
      cell: (s) => (
        <span className="capitalize">{s.payment_method || <span className="text-muted-foreground">—</span>}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      cell: (s) => <StatusBadge tone={defaultStatusTone(s.status)}>{s.status}</StatusBadge>,
    },
    {
      key: 'total',
      header: 'Total',
      sortable: true,
      numeric: true,
      cell: (s) => formatCurrency(s.total),
    },
    {
      key: 'contribution_margin',
      header: 'Margin',
      numeric: true,
      colClassName: 'hidden md:table-cell',
      cell: (s) => (
        <span className={Number(s.contribution_margin) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}>
          {formatCurrency(s.contribution_margin)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sales"
        description={`${total.toLocaleString()} ${total === 1 ? 'result' : 'results'}`}
        actions={
          <Button asChild>
            <Link to="/sell/sales/new">
              <Plus className="h-4 w-4" /> New sale
            </Link>
          </Button>
        }
      />

      {/* Desktop: DataTable with integrated toolbar + pagination */}
      <div className="hidden md:block">
        <DataTable<SaleListItem>
          data={sales}
          columns={columns}
          rowKey={(s) => s.id}
          onRowClick={(s) => navigate(`/sell/sales/${s.id}`)}
          sortKey={sortKey}
          sortDir={sortDir}
          onSortChange={handleSortChange}
          selectable
          selected={selected}
          onSelectedChange={setSelected}
          loading={isLoading}
          emptyState={
            activeFilters > 0
              ? 'No sales match the current filters.'
              : 'No sales recorded yet.'
          }
          toolbar={
            <TableToolbar
              total={total}
              activeFilters={activeFilters}
              onClearFilters={clearFilters}
              actions={
                selected.size > 0 ? (
                  <button
                    type="button"
                    onClick={exportSelected}
                    className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export {selected.size} selected
                  </button>
                ) : null
              }
            >
              <SearchInput
                value={search}
                onChange={(v) => {
                  setSearch(v);
                  setPage(0);
                }}
                placeholder="Search by sale # or customer…"
              />
              <Select
                value={status}
                onChange={(v) => {
                  setStatus(v);
                  setPage(0);
                }}
                options={STATUS_OPTIONS}
                placeholder="All statuses"
                aria-label="Filter by status"
              />
              <Select
                value={channelId}
                onChange={(v) => {
                  setChannelId(v);
                  setPage(0);
                }}
                options={(channels || []).map((c) => ({ value: c.id, label: c.name }))}
                placeholder="All channels"
                aria-label="Filter by channel"
              />
              <Select
                value={paymentMethod}
                onChange={(v) => {
                  setPaymentMethod(v);
                  setPage(0);
                }}
                options={paymentMethods.map((m) => ({ value: m, label: m }))}
                placeholder="All payment methods"
                aria-label="Filter by payment method"
              />
            </TableToolbar>
          }
          footer={
            <Pagination
              page={page}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              onPageSizeChange={(n) => {
                setPageSize(n);
                setPage(0);
              }}
            />
          }
        />
      </div>

      {/* Mobile: card list, unchanged */}
      <div className="md:hidden space-y-3">
        {sales.map((s) => (
          <Link
            key={s.id}
            to={`/sell/sales/${s.id}`}
            className="block bg-card border border-border rounded-md p-4 no-underline"
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="font-semibold">{s.sale_number}</p>
                <p className="text-xs text-muted-foreground">
                  {s.date} &middot; {s.customer_name || 'No customer'}
                </p>
              </div>
              <StatusBadge tone={defaultStatusTone(s.status)}>{s.status}</StatusBadge>
            </div>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Total</p>
                <p className="tabular-nums">{formatCurrency(s.total)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Margin</p>
                <p
                  className={cn(
                    'tabular-nums',
                    Number(s.contribution_margin) >= 0
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-destructive',
                  )}
                >
                  {formatCurrency(s.contribution_margin)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Payment</p>
                <p className="capitalize">{s.payment_method || '—'}</p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              {s.channel_name || 'Direct'} &middot; {s.item_count} items
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}

