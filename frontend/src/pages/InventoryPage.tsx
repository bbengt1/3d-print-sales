import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  ClipboardCheck,
  Layers,
  Plus,
  ScrollText,
  TriangleAlert,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Label } from '@/components/ui/Label';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import PageHeader from '@/components/layout/PageHeader';
import { KPI, KPIStrip } from '@/components/layout/KPIStrip';
import DataTable, { type Column, type SortDir } from '@/components/data/DataTable';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import SearchInput from '@/components/data/SearchInput';
import SelectInput from '@/components/data/Select';
import Pagination from '@/components/data/Pagination';
import { cn, formatCurrency } from '@/lib/utils';
import type {
  InventoryAlert,
  InventoryReconcileResponse,
  InventoryTransaction,
  PaginatedProducts,
  PaginatedTransactions,
} from '@/types';

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'production', label: 'Production' },
  { value: 'sale', label: 'Sale' },
  { value: 'adjustment', label: 'Adjustment' },
  { value: 'return', label: 'Return' },
  { value: 'waste', label: 'Waste' },
] as const;

type StockSurface = 'exceptions' | 'ledger';

export default function InventoryPage() {
  const queryClient = useQueryClient();
  const [surface, setSurface] = useState<StockSurface>('exceptions');
  const [search, setSearch] = useState('');
  const [type, setType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sortKey, setSortKey] = useState<string>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [showReconcile, setShowReconcile] = useState(false);
  const [reconcileSaving, setReconcileSaving] = useState(false);
  const [reconcileForm, setReconcileForm] = useState({ product_id: '', counted_qty: 0, reason: '', notes: '' });
  const [showAdjust, setShowAdjust] = useState(false);
  const [adjustSaving, setAdjustSaving] = useState(false);
  const [adjustForm, setAdjustForm] = useState({ product_id: '', type: 'adjustment', quantity: 0, notes: '' });

  const params = useMemo(
    () => ({
      skip: page * pageSize,
      limit: pageSize,
      sort_by: sortKey || undefined,
      sort_dir: sortDir,
      ...(search ? { search } : {}),
      ...(type ? { type } : {}),
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
    }),
    [page, pageSize, sortKey, sortDir, search, type, dateFrom, dateTo],
  );

  const { data, isLoading } = useQuery<PaginatedTransactions>({
    queryKey: ['inventory-transactions', params],
    queryFn: () => api.get('/inventory/transactions', { params }).then((r) => r.data),
  });

  const { data: alerts = [] } = useQuery<InventoryAlert[]>({
    queryKey: ['inventory-alerts'],
    queryFn: () => api.get('/inventory/alerts').then((r) => r.data),
  });

  const { data: productsData } = useQuery<PaginatedProducts>({
    queryKey: ['products', 'inventory-reconcile'],
    queryFn: () => api.get('/products?is_active=true&limit=200').then((r) => r.data),
  });

  const products = productsData?.items || [];
  const items = data?.items || [];
  const selectedProduct = products.find((product) => product.id === reconcileForm.product_id) || null;
  const adjustProduct = products.find((product) => product.id === adjustForm.product_id) || null;
  const variance = selectedProduct ? reconcileForm.counted_qty - selectedProduct.stock_qty : 0;

  const productAlerts = alerts.filter((alert) => alert.type === 'product');
  const materialAlerts = alerts.filter((alert) => alert.type !== 'product');
  const criticalProductAlerts = productAlerts.filter((alert) => alert.current_stock <= 0);
  const outOfStockProducts = products.filter((product) => product.stock_qty <= 0);
  const nearReorderProducts = products.filter(
    (product) => product.stock_qty > 0 && product.stock_qty <= product.reorder_point,
  );
  const recentRiskTransactions = items
    .filter((transaction) => transaction.type === 'adjustment' || transaction.type === 'waste')
    .slice(0, 5);

  const openReconcile = (productId?: string) => {
    const presetProduct = products.find((product) => product.id === productId);
    setReconcileForm({
      product_id: productId || '',
      counted_qty: presetProduct?.stock_qty || 0,
      reason: '',
      notes: '',
    });
    setShowReconcile(true);
  };

  const openAdjust = (productId?: string) => {
    setAdjustForm({ product_id: productId || '', type: 'adjustment', quantity: 0, notes: '' });
    setShowAdjust(true);
  };

  const submitReconcile = async () => {
    if (!reconcileForm.product_id) {
      toast.error('Select a product');
      return;
    }
    if (!reconcileForm.reason.trim()) {
      toast.error('Reason is required');
      return;
    }
    setReconcileSaving(true);
    try {
      const { data } = await api.post<InventoryReconcileResponse>('/inventory/reconcile', reconcileForm);
      toast.success(data.detail);
      setShowReconcile(false);
      queryClient.invalidateQueries({ queryKey: ['inventory-transactions'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-alerts'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to reconcile inventory');
    } finally {
      setReconcileSaving(false);
    }
  };

  const submitAdjust = async () => {
    if (!adjustForm.product_id) {
      toast.error('Select a product');
      return;
    }
    if (adjustForm.quantity === 0) {
      toast.error('Quantity cannot be 0');
      return;
    }
    if (adjustForm.type === 'adjustment' && !adjustForm.notes.trim()) {
      toast.error('Adjustment notes are required');
      return;
    }
    setAdjustSaving(true);
    try {
      await api.post('/inventory/transactions', {
        product_id: adjustForm.product_id,
        type: adjustForm.type,
        quantity: adjustForm.quantity,
        unit_cost: adjustProduct?.unit_cost || 0,
        notes: adjustForm.notes || null,
      });
      toast.success('Stock adjustment submitted');
      setShowAdjust(false);
      queryClient.invalidateQueries({ queryKey: ['inventory-transactions'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-alerts'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to adjust stock');
    } finally {
      setAdjustSaving(false);
    }
  };

  // Product exceptions table columns
  const exceptionColumns: Column<InventoryAlert>[] = [
    {
      key: 'name',
      header: 'Product',
      cell: (a) => <span className="font-medium text-foreground">{a.name}</span>,
    },
    {
      key: 'sku',
      header: 'SKU',
      colClassName: 'hidden md:table-cell',
      cell: (a) => <span className="font-mono text-xs text-muted-foreground">{a.sku || '—'}</span>,
    },
    {
      key: 'current_stock',
      header: 'Stock',
      numeric: true,
      cell: (a) => (
        <span className={a.current_stock <= 0 ? 'font-semibold text-destructive' : 'text-amber-700 dark:text-amber-300'}>
          {a.current_stock}
        </span>
      ),
    },
    {
      key: 'reorder_point',
      header: 'Reorder',
      numeric: true,
      colClassName: 'hidden md:table-cell',
      cell: (a) => <span className="text-muted-foreground">{a.reorder_point}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      cell: (a) => (
        <StatusBadge tone={a.current_stock <= 0 ? 'destructive' : 'warning'}>
          {a.current_stock <= 0 ? 'Stockout' : 'Reorder risk'}
        </StatusBadge>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '240px',
      cell: (a) => (
        <div className="flex justify-end gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              openAdjust(a.id);
            }}
          >
            Adjust
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              openReconcile(a.id);
            }}
          >
            Reconcile
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to={`/product-studio/products/${a.id}`} onClick={(e) => e.stopPropagation()}>
              View
            </Link>
          </Button>
        </div>
      ),
    },
  ];

  // Ledger columns
  const ledgerColumns: Column<InventoryTransaction>[] = [
    {
      key: 'created_at',
      header: 'Date',
      sortable: true,
      cell: (t) => (
        <span className="text-xs tabular-nums text-muted-foreground">
          {t.created_at ? new Date(t.created_at).toLocaleString() : '—'}
        </span>
      ),
    },
    {
      key: 'product_name',
      header: 'Product',
      cell: (t) =>
        t.product_name ? (
          <Link
            className="font-medium text-foreground no-underline hover:underline"
            to={`/products/${t.product_id}`}
          >
            {t.product_name}
          </Link>
        ) : (
          <span className="font-mono text-xs">{t.product_id}</span>
        ),
    },
    {
      key: 'product_sku',
      header: 'SKU',
      colClassName: 'hidden lg:table-cell',
      cell: (t) => <span className="font-mono text-xs">{t.product_sku || '—'}</span>,
    },
    {
      key: 'type',
      header: 'Type',
      sortable: true,
      cell: (t) => <StatusBadge tone={defaultStatusTone(t.type)}>{t.type}</StatusBadge>,
    },
    {
      key: 'quantity',
      header: 'Qty',
      sortable: true,
      numeric: true,
      cell: (t) => (
        <span
          className={cn(
            'font-medium',
            t.quantity > 0
              ? 'text-emerald-600 dark:text-emerald-400'
              : t.quantity < 0
                ? 'text-destructive'
                : 'text-foreground',
          )}
        >
          {t.quantity > 0 ? '+' : ''}
          {t.quantity}
        </span>
      ),
    },
    {
      key: 'unit_cost',
      header: 'Unit cost',
      sortable: true,
      numeric: true,
      colClassName: 'hidden md:table-cell',
      cell: (t) => formatCurrency(t.unit_cost),
    },
    {
      key: 'job_id',
      header: 'Job',
      colClassName: 'hidden xl:table-cell',
      cell: (t) => <span className="font-mono text-xs">{t.job_id || '—'}</span>,
    },
    {
      key: 'notes',
      header: 'Notes',
      colClassName: 'hidden xl:table-cell',
      cell: (t) => <span className="text-xs text-muted-foreground">{t.notes || '—'}</span>,
    },
  ];

  const activeFilters = [search, type, dateFrom, dateTo].filter(Boolean).length;
  const clearFilters = () => {
    setSearch('');
    setType('');
    setDateFrom('');
    setDateTo('');
    setPage(0);
  };
  const handleSortChange = (key: string, dir: SortDir | null) => {
    if (!key || !dir) {
      setSortKey('created_at');
      setSortDir('desc');
    } else {
      setSortKey(key);
      setSortDir(dir);
    }
    setPage(0);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Stock"
        description={
          productAlerts.length > 0
            ? `${productAlerts.length} ${productAlerts.length === 1 ? 'item needs' : 'items need'} attention`
            : 'Exceptions first — stock problems affecting selling and fulfillment.'
        }
        actions={
          <>
            <Button variant="outline" onClick={() => openAdjust()}>
              <Plus className="h-4 w-4" /> Quick adjustment
            </Button>
            <Button onClick={() => openReconcile()}>
              <ClipboardCheck className="h-4 w-4" /> Reconcile stock
            </Button>
          </>
        }
      >
        <KPIStrip columns={4}>
          <KPI
            label="Product alerts"
            value={productAlerts.length}
            sub="POS and finished-goods issues"
            tone={productAlerts.length > 0 ? 'warning' : 'default'}
          />
          <KPI
            label="Critical stockouts"
            value={criticalProductAlerts.length}
            sub="Products at zero stock"
            tone={criticalProductAlerts.length > 0 ? 'destructive' : 'default'}
          />
          <KPI
            label="Near reorder"
            value={nearReorderProducts.length}
            sub="Nearing depletion"
            tone={nearReorderProducts.length > 0 ? 'warning' : 'default'}
          />
          <KPI label="Material signals" value={materialAlerts.length} sub="Raw-material alerts" />
        </KPIStrip>
      </PageHeader>

      {/* Reconcile dialog */}
      <Dialog open={showReconcile} onOpenChange={(open) => !open && setShowReconcile(false)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Stock reconciliation</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="reconcile-product">Product *</Label>
              <select
                id="reconcile-product"
                value={reconcileForm.product_id}
                onChange={(event) => setReconcileForm((form) => ({ ...form, product_id: event.target.value }))}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Select product…</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} ({product.sku})
                  </option>
                ))}
              </select>
            </div>

            {selectedProduct ? (
              <div className="grid grid-cols-2 gap-4 rounded-md bg-muted px-4 py-3 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground">Current system qty</p>
                  <p className="mt-0.5 text-lg font-semibold tabular-nums">{selectedProduct.stock_qty}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Variance</p>
                  <p
                    className={cn(
                      'mt-0.5 text-lg font-semibold tabular-nums',
                      variance > 0 && 'text-emerald-600 dark:text-emerald-400',
                      variance < 0 && 'text-destructive',
                    )}
                  >
                    {variance > 0 ? '+' : ''}
                    {variance}
                  </p>
                </div>
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="reconcile-counted">Counted quantity *</Label>
              <Input
                id="reconcile-counted"
                type="number"
                min="0"
                value={reconcileForm.counted_qty}
                onChange={(event) =>
                  setReconcileForm((form) => ({ ...form, counted_qty: Number(event.target.value) }))
                }
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="reconcile-reason">Reason *</Label>
              <Input
                id="reconcile-reason"
                value={reconcileForm.reason}
                onChange={(event) => setReconcileForm((form) => ({ ...form, reason: event.target.value }))}
                placeholder="Cycle count, shelf recount, received correction…"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="reconcile-notes">Notes</Label>
              <Textarea
                id="reconcile-notes"
                value={reconcileForm.notes}
                onChange={(event) => setReconcileForm((form) => ({ ...form, notes: event.target.value }))}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReconcile(false)}>
              Cancel
            </Button>
            <Button onClick={submitReconcile} disabled={reconcileSaving}>
              {reconcileSaving ? 'Submitting…' : 'Submit reconciliation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Adjust dialog */}
      <Dialog open={showAdjust} onOpenChange={(open) => !open && setShowAdjust(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Quick stock adjustment</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="adjust-product">Product *</Label>
              <select
                id="adjust-product"
                value={adjustForm.product_id}
                onChange={(event) => setAdjustForm((form) => ({ ...form, product_id: event.target.value }))}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Select product…</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} ({product.sku})
                  </option>
                ))}
              </select>
            </div>

            {adjustProduct ? (
              <div className="rounded-md bg-muted px-4 py-3 text-sm">
                <p className="text-xs text-muted-foreground">Current stock</p>
                <p className="mt-0.5 text-lg font-semibold tabular-nums">{adjustProduct.stock_qty}</p>
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="adjust-type">Type</Label>
              <select
                id="adjust-type"
                value={adjustForm.type}
                onChange={(event) => setAdjustForm((form) => ({ ...form, type: event.target.value }))}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {TYPE_OPTIONS.filter((option) => option.value).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="adjust-quantity">Quantity *</Label>
              <Input
                id="adjust-quantity"
                type="number"
                value={adjustForm.quantity}
                onChange={(event) => setAdjustForm((form) => ({ ...form, quantity: Number(event.target.value) }))}
                placeholder="Positive to add, negative to remove"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="adjust-notes">Notes</Label>
              <Textarea
                id="adjust-notes"
                value={adjustForm.notes}
                onChange={(event) => setAdjustForm((form) => ({ ...form, notes: event.target.value }))}
                rows={3}
                placeholder="Reason for adjustment"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdjust(false)}>
              Cancel
            </Button>
            <Button onClick={submitAdjust} disabled={adjustSaving}>
              {adjustSaving ? 'Submitting…' : 'Submit adjustment'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Surface switcher */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={surface} onValueChange={(v) => setSurface(v as StockSurface)}>
          <TabsList>
            <TabsTrigger value="exceptions">
              Exceptions
              <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">{productAlerts.length}</span>
            </TabsTrigger>
            <TabsTrigger value="ledger">
              Ledger
              <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">{data?.total ?? 0}</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <Button asChild variant="outline" size="sm">
          <Link to="/stock/materials">
            <Layers className="h-3.5 w-3.5" /> Materials
          </Link>
        </Button>
      </div>

      {surface === 'exceptions' ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <TriangleAlert className="h-4 w-4 text-destructive" aria-hidden="true" />
              <h2 className="text-base font-semibold">Product exceptions</h2>
            </div>
            <DataTable<InventoryAlert>
              data={productAlerts}
              columns={exceptionColumns}
              rowKey={(a) => a.id}
              emptyState="No product exceptions — finished-goods stock is above its urgent threshold."
              toolbar={<TableToolbar total={productAlerts.length} />}
            />
          </section>

          <aside className="space-y-4">
            {outOfStockProducts.length > 0 || nearReorderProducts.length > 0 ? (
              <section className="rounded-md border border-border bg-card p-4 shadow-xs">
                <h2 className="mb-3 text-sm font-semibold">Finished-goods breakdown</h2>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center justify-between">
                    <span className="text-muted-foreground">Out of stock</span>
                    <span
                      className={cn(
                        'font-semibold tabular-nums',
                        outOfStockProducts.length > 0 ? 'text-destructive' : 'text-foreground',
                      )}
                    >
                      {outOfStockProducts.length}
                    </span>
                  </li>
                  <li className="flex items-center justify-between">
                    <span className="text-muted-foreground">Near reorder</span>
                    <span
                      className={cn(
                        'font-semibold tabular-nums',
                        nearReorderProducts.length > 0
                          ? 'text-amber-700 dark:text-amber-300'
                          : 'text-foreground',
                      )}
                    >
                      {nearReorderProducts.length}
                    </span>
                  </li>
                </ul>
              </section>
            ) : null}

            <section className="rounded-md border border-border bg-card p-4 shadow-xs">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <ScrollText className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  <h2 className="text-sm font-semibold">Recent risky movements</h2>
                </div>
                <button
                  type="button"
                  onClick={() => setSurface('ledger')}
                  className="text-xs text-primary hover:underline"
                >
                  Open ledger <ArrowRight className="inline h-3 w-3" />
                </button>
              </div>
              {recentRiskTransactions.length === 0 ? (
                <p className="text-sm text-muted-foreground">No recent adjustments or waste entries.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {recentRiskTransactions.map((transaction) => (
                    <li key={transaction.id} className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-foreground">
                          {transaction.product_name || transaction.product_id}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          {transaction.created_at ? new Date(transaction.created_at).toLocaleString() : '—'}
                          {transaction.notes ? ` · ${transaction.notes}` : ''}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <StatusBadge tone={defaultStatusTone(transaction.type)} hideDot>
                          {transaction.type}
                        </StatusBadge>
                        <span
                          className={cn(
                            'font-semibold tabular-nums',
                            transaction.quantity > 0
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : 'text-destructive',
                          )}
                        >
                          {transaction.quantity > 0 ? '+' : ''}
                          {transaction.quantity}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {materialAlerts.length > 0 ? (
              <section className="rounded-md border border-amber-300/60 bg-amber-50/80 p-4 dark:border-amber-500/30 dark:bg-amber-500/10">
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-amber-800 dark:text-amber-300">Material signals</h2>
                  <Button asChild variant="ghost" size="sm" className="h-6 px-2 text-xs">
                    <Link to="/stock/materials">Open</Link>
                  </Button>
                </div>
                <ul className="space-y-1 text-sm">
                  {materialAlerts.slice(0, 6).map((alert) => (
                    <li key={`${alert.type}-${alert.id}`} className="flex items-center justify-between gap-3">
                      <Link
                        to="/stock/materials"
                        className="truncate text-foreground no-underline hover:underline"
                      >
                        {alert.name}
                      </Link>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {alert.current_stock} / {alert.reorder_point}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </aside>
        </div>
      ) : (
        <DataTable<InventoryTransaction>
          data={items}
          columns={ledgerColumns}
          rowKey={(t) => t.id}
          sortKey={sortKey}
          sortDir={sortDir}
          onSortChange={handleSortChange}
          loading={isLoading}
          emptyState={activeFilters > 0 ? 'No transactions match these filters.' : 'No inventory transactions yet.'}
          toolbar={
            <TableToolbar total={data?.total ?? 0} activeFilters={activeFilters} onClearFilters={clearFilters}>
              <SearchInput
                value={search}
                onChange={(v) => {
                  setSearch(v);
                  setPage(0);
                }}
                placeholder="Search product or SKU…"
              />
              <SelectInput
                value={type}
                onChange={(v) => {
                  setType(v);
                  setPage(0);
                }}
                options={TYPE_OPTIONS.filter((o) => o.value).map((o) => ({ value: o.value, label: o.label }))}
                placeholder="All types"
                aria-label="Filter by type"
              />
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setPage(0);
                }}
                className="w-auto"
                aria-label="From date"
              />
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setPage(0);
                }}
                className="w-auto"
                aria-label="To date"
              />
            </TableToolbar>
          }
          footer={
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data?.total ?? 0}
              onPageChange={setPage}
              onPageSizeChange={(n) => {
                setPageSize(n);
                setPage(0);
              }}
            />
          }
        />
      )}

      <div className="sr-only" aria-live="polite">
        Stock surface: {surface}
      </div>
    </div>
  );
}
