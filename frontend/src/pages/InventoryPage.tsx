import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  ClipboardCheck,
  Clock3,
  PackageSearch,
  Plus,
  ScrollText,
  TrendingDown,
  TriangleAlert,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Label } from '@/components/ui/Label';
import EmptyState from '@/components/ui/EmptyState';
import PageHeader from '@/components/layout/PageHeader';
import { KPI, KPIStrip } from '@/components/layout/KPIStrip';
import DataTable, { type Column, type SortDir } from '@/components/data/DataTable';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import SearchInput from '@/components/data/SearchInput';
import Select from '@/components/data/Select';
import Pagination from '@/components/data/Pagination';
import { cn, formatCurrency } from '@/lib/utils';
import type { InventoryAlert, InventoryReconcileResponse, InventoryTransaction, PaginatedProducts, PaginatedTransactions } from '@/types';

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'production', label: 'Production' },
  { value: 'sale', label: 'Sale' },
  { value: 'adjustment', label: 'Adjustment' },
  { value: 'return', label: 'Return' },
  { value: 'waste', label: 'Waste' },
] as const;

type StockSurface = 'exceptions' | 'ledger';

interface SurfaceButtonProps {
  active: boolean;
  label: string;
  detail: string;
  onClick: () => void;
}

function SurfaceButton({ active, label, detail, onClick }: SurfaceButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-md border px-4 py-3 text-left transition-colors',
        active
          ? 'border-primary bg-primary text-primary-foreground shadow-sm'
          : 'border-border bg-background/80 text-foreground hover:border-primary/35'
      )}
    >
      <p className="text-sm font-semibold">{label}</p>
      <p className={cn('mt-1 text-xs', active ? 'text-primary-foreground/80' : 'text-muted-foreground')}>{detail}</p>
    </button>
  );
}


function TaskCard({
  title,
  detail,
  actionLabel,
  onAction,
  tone = 'default',
}: {
  title: string;
  detail: string;
  actionLabel: string;
  onAction: () => void;
  tone?: 'default' | 'warning';
}) {
  return (
    <div
      className={cn(
        'rounded-lg border p-5 shadow-sm',
        tone === 'warning' ? 'border-amber-300/70 bg-amber-50' : 'border-border bg-card'
      )}
    >
      <p className="text-lg font-semibold">{title}</p>
      <p className={cn('mt-2 text-sm', tone === 'warning' ? 'text-amber-900/80' : 'text-muted-foreground')}>{detail}</p>
      <button
        type="button"
        onClick={onAction}
        className={cn(
          'mt-4 inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition-colors',
          tone === 'warning'
            ? 'bg-amber-900 text-white hover:opacity-90'
            : 'bg-primary text-primary-foreground hover:opacity-90'
        )}
      >
        {actionLabel}
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function InventoryPage() {
  const navigate = useNavigate();
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
    [page, pageSize, sortKey, sortDir, search, type, dateFrom, dateTo]
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
    (product) => product.stock_qty > 0 && product.stock_qty <= product.reorder_point
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

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <PageHeader
        title="Inventory"
        description={
          productAlerts.length > 0
            ? `${productAlerts.length} ${productAlerts.length === 1 ? 'item needs' : 'items need'} attention`
            : 'Exceptions first — stock problems affecting selling and fulfillment'
        }
        actions={
          <>
            <Button type="button" onClick={() => openReconcile()}>
              <ClipboardCheck className="h-4 w-4" />
              Reconcile stock
            </Button>
            <button
              type="button"
              onClick={() => openAdjust()}
              className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
            >
              <Plus className="h-4 w-4" />
              Quick adjustment
            </button>
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
          <KPI
            label="Material signals"
            value={materialAlerts.length}
            sub="Lower-priority issues"
          />
        </KPIStrip>
      </PageHeader>

      <Dialog open={showReconcile} onOpenChange={(open) => !open && setShowReconcile(false)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Stock reconciliation</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="reconcile-product">Product</Label>
              <select
                id="reconcile-product"
                value={reconcileForm.product_id}
                onChange={(event) => setReconcileForm((form) => ({ ...form, product_id: event.target.value }))}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Select product...</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} ({product.sku})
                  </option>
                ))}
              </select>
            </div>

            {selectedProduct ? (
              <div className="grid grid-cols-2 gap-4 rounded-xl bg-accent/40 p-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Current system qty</p>
                  <p className="text-lg font-semibold">{selectedProduct.stock_qty}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Variance</p>
                  <p
                    className={cn(
                      'text-lg font-semibold',
                      variance > 0 && 'text-green-600 dark:text-green-400',
                      variance < 0 && 'text-red-600 dark:text-red-400'
                    )}
                  >
                    {variance > 0 ? '+' : ''}
                    {variance}
                  </p>
                </div>
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="reconcile-counted-qty">Counted quantity</Label>
              <Input
                id="reconcile-counted-qty"
                type="number"
                min="0"
                value={reconcileForm.counted_qty}
                onChange={(event) =>
                  setReconcileForm((form) => ({ ...form, counted_qty: Number(event.target.value) }))
                }
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="reconcile-reason">Reason</Label>
              <Input
                id="reconcile-reason"
                value={reconcileForm.reason}
                onChange={(event) => setReconcileForm((form) => ({ ...form, reason: event.target.value }))}
                placeholder="Cycle count, shelf recount, received correction..."
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
            <Button variant="outline" onClick={() => setShowReconcile(false)}>Cancel</Button>
            <Button onClick={submitReconcile} disabled={reconcileSaving}>
              {reconcileSaving ? 'Submitting…' : 'Submit reconciliation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showAdjust} onOpenChange={(open) => !open && setShowAdjust(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Quick stock adjustment</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="adjust-product">Product</Label>
              <select
                id="adjust-product"
                value={adjustForm.product_id}
                onChange={(event) => setAdjustForm((form) => ({ ...form, product_id: event.target.value }))}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Select product...</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} ({product.sku})
                  </option>
                ))}
              </select>
            </div>

            {adjustProduct ? (
              <div className="rounded-xl bg-accent/40 p-3 text-sm">
                <p className="text-muted-foreground">Current stock</p>
                <p className="text-lg font-semibold">{adjustProduct.stock_qty}</p>
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
              <Label htmlFor="adjust-quantity">Quantity</Label>
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
            <Button variant="outline" onClick={() => setShowAdjust(false)}>Cancel</Button>
            <Button onClick={submitAdjust} disabled={adjustSaving}>
              {adjustSaving ? 'Submitting…' : 'Submit adjustment'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TaskCard
          title="Cycle counts"
          detail="Start a reconciliation without digging through historical transactions first."
          actionLabel="Open reconcile"
          onAction={() => openReconcile()}
        />
        <TaskCard
          title="Manual correction"
          detail="Record a quick adjustment when the shelf count is already understood."
          actionLabel="Open adjustment"
          onAction={() => openAdjust()}
        />
        <TaskCard
          title="Materials lane"
          detail="Material spool inventory is still available, but it stays out of the urgent product queue."
          actionLabel="Open materials"
          onAction={() => navigate('/stock/materials')}
        />
        <TaskCard
          title="Risk ledger"
          detail="Recent waste and adjustment entries are visible below, with the full ledger one tap away."
          actionLabel="Open ledger"
          onAction={() => setSurface('ledger')}
          tone="warning"
        />
      </section>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-muted-foreground">Workspace Surfaces</p>
            <h2 className="mt-2 text-2xl font-semibold">Stock home</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Exceptions stay above the fold. The ledger is still accessible, but it is now a deliberate secondary view.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <SurfaceButton
              active={surface === 'exceptions'}
              label="Exceptions"
              detail="Urgent inventory issues and task-driven actions"
              onClick={() => setSurface('exceptions')}
            />
            <SurfaceButton
              active={surface === 'ledger'}
              label="Ledger"
              detail="Historical transaction search and audit trail"
              onClick={() => setSurface('ledger')}
            />
          </div>
        </div>
      </section>

      {surface === 'exceptions' ? (
        <div className="space-y-6">
          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.9fr)]">
            <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <TriangleAlert className="h-5 w-5 text-destructive" />
                <h2 className="text-xl font-semibold">Product exceptions</h2>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                These issues affect sellable finished goods first. Product-impacting stock problems stay visually separate from raw-material status.
              </p>

              {!productAlerts.length ? (
                <EmptyState
                  icon="products"
                  title="No product exceptions"
                  description="Finished-goods stock is currently above its urgent exception threshold."
                  className="py-10"
                />
              ) : (
                <div className="mt-4 space-y-3">
                  {productAlerts.map((alert) => {
                    const isCritical = alert.current_stock <= 0;
                    return (
                      <div
                        key={`${alert.type}-${alert.id}`}
                        className={cn(
                          'rounded-md border p-4',
                          isCritical ? 'border-destructive/35 bg-destructive/5' : 'border-amber-300/60 bg-amber-50/70'
                        )}
                      >
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold">{alert.name}</p>
                              <StatusBadge tone={isCritical ? 'destructive' : 'warning'}>
                                {isCritical ? 'Stockout' : 'Reorder risk'}
                              </StatusBadge>
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">
                              {(alert.sku || 'No SKU')} • Stock {alert.current_stock} / Reorder {alert.reorder_point}
                            </p>
                          </div>

                          <div className="flex flex-wrap gap-2 text-sm">
                            <Button type="button" onClick={() => openAdjust(alert.id)}>
                              Adjust
                            </Button>
                            <button
                              type="button"
                              onClick={() => openReconcile(alert.id)}
                              className="rounded-xl border border-border px-3 py-2 font-semibold transition-colors hover:bg-accent"
                            >
                              Reconcile
                            </button>
                            <Link
                              className="inline-flex items-center rounded-xl border border-border px-3 py-2 font-semibold text-foreground no-underline transition-colors hover:bg-accent"
                              to={`/product-studio/products/${alert.id}`}
                            >
                              View product
                            </Link>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
                <div className="flex items-center gap-2">
                  <PackageSearch className="h-5 w-5 text-muted-foreground" />
                  <h2 className="text-xl font-semibold">Exception summary</h2>
                </div>
                <div className="mt-4 space-y-3">
                  <div className="rounded-md bg-background px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Out of stock</p>
                    <p className="mt-2 text-2xl font-semibold">{outOfStockProducts.length}</p>
                    <p className="mt-1 text-sm text-muted-foreground">Products that cannot be sold from POS right now.</p>
                  </div>
                  <div className="rounded-md bg-background px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Near reorder</p>
                    <p className="mt-2 text-2xl font-semibold">{nearReorderProducts.length}</p>
                    <p className="mt-1 text-sm text-muted-foreground">Products that still have stock but need floor attention soon.</p>
                  </div>
                  <div className="rounded-md bg-background px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Material signals</p>
                    <p className="mt-2 text-2xl font-semibold">{materialAlerts.length}</p>
                    <p className="mt-1 text-sm text-muted-foreground">Raw-material alerts kept in a separate lane.</p>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
                <div className="flex items-center gap-2">
                  <ScrollText className="h-5 w-5 text-muted-foreground" />
                  <h2 className="text-xl font-semibold">Recent risky movements</h2>
                </div>

                {!recentRiskTransactions.length ? (
                  <p className="mt-4 text-sm text-muted-foreground">No recent adjustment or waste transactions in the current ledger window.</p>
                ) : (
                  <div className="mt-4 space-y-3">
                    {recentRiskTransactions.map((transaction) => (
                      <div key={transaction.id} className="rounded-md border border-border bg-background/80 px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium">{transaction.product_name || transaction.product_id}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {transaction.created_at ? new Date(transaction.created_at).toLocaleString() : '-'}
                            </p>
                          </div>
                          <StatusBadge tone={defaultStatusTone(transaction.type)}>{transaction.type}</StatusBadge>
                        </div>
                        <div className="mt-3 flex items-center justify-between text-sm">
                          <p className="text-muted-foreground">{transaction.notes || 'No notes provided'}</p>
                          <p className={cn('font-semibold', transaction.quantity < 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400')}>
                            {transaction.quantity > 0 ? '+' : ''}
                            {transaction.quantity}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => setSurface('ledger')}
                  className="mt-4 inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm font-semibold transition-colors hover:bg-accent"
                >
                  Open full ledger
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <TrendingDown className="h-5 w-5 text-amber-600" />
                <h2 className="text-xl font-semibold">Materials lane</h2>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                Material shortages still matter, but they are separated from finished-goods actions so the stock workspace favors immediate selling and fulfillment risk first.
              </p>

              {!materialAlerts.length ? (
                <p className="mt-4 text-sm text-muted-foreground">No material-specific low-stock alerts right now.</p>
              ) : (
                <div className="mt-4 space-y-3">
                  {materialAlerts.map((alert) => (
                    <div key={`${alert.type}-${alert.id}`} className="rounded-md border border-border bg-background/80 px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium">{alert.name}</p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            Stock {alert.current_stock} / Reorder {alert.reorder_point}
                          </p>
                        </div>
                        <Link
                          to="/stock/materials"
                          className="inline-flex items-center rounded-xl border border-border px-3 py-2 text-sm font-semibold text-foreground no-underline transition-colors hover:bg-accent"
                        >
                          View materials
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <Clock3 className="h-5 w-5 text-muted-foreground" />
                <h2 className="text-xl font-semibold">Quick reminders</h2>
              </div>
              <div className="mt-4 space-y-3 text-sm text-muted-foreground">
                <p>Reconcile when the shelf count is uncertain.</p>
                <p>Use quick adjustment only when the count is already understood.</p>
                <p>Finished-product issues should be handled before material-only cleanup.</p>
              </div>
            </div>
          </section>
        </div>
      ) : (
        (() => {
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
          const ledgerColumns: Column<InventoryTransaction>[] = [
            {
              key: 'created_at',
              header: 'Date',
              sortable: true,
              cell: (t) => (
                <span className="text-xs tabular-nums">
                  {t.created_at ? new Date(t.created_at).toLocaleString() : '—'}
                </span>
              ),
            },
            {
              key: 'product_name',
              header: 'Product',
              cell: (t) =>
                t.product_name ? (
                  <Link className="font-medium no-underline hover:underline" to={`/products/${t.product_id}`}>
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
                <span className={t.quantity > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}>
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

          return (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ScrollText className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-base font-semibold">Inventory ledger</h2>
                </div>
                <button
                  type="button"
                  onClick={() => setSurface('exceptions')}
                  className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
                >
                  Back to exceptions
                </button>
              </div>

              <DataTable<InventoryTransaction>
                data={items}
                columns={ledgerColumns}
                rowKey={(t) => t.id}
                sortKey={sortKey}
                sortDir={sortDir}
                onSortChange={handleSortChange}
                loading={isLoading}
                emptyState={activeFilters > 0 ? 'No transactions match these filters.' : 'No inventory transactions recorded yet.'}
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
                    <Select
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
            </div>
          );
        })()
      )}

      <div className="sr-only" aria-live="polite">
        Stock surface: {surface}
      </div>
    </div>
  );
}
