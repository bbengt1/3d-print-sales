import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  Boxes,
  ClipboardCheck,
  Clock3,
  PackageSearch,
  Plus,
  ScrollText,
  TrendingDown,
  TriangleAlert,
  X,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import EmptyState from '@/components/ui/EmptyState';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { cn, formatCurrency } from '@/lib/utils';
import type { InventoryAlert, InventoryReconcileResponse, PaginatedProducts, PaginatedTransactions } from '@/types';

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'production', label: 'Production' },
  { value: 'sale', label: 'Sale' },
  { value: 'adjustment', label: 'Adjustment' },
  { value: 'return', label: 'Return' },
  { value: 'waste', label: 'Waste' },
] as const;

const TYPE_COLORS: Record<string, string> = {
  production: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  sale: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  adjustment: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  return: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
  waste: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

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

interface HeroMetricProps {
  label: string;
  value: string;
  detail: string;
}

function HeroMetric({ label, value, detail }: HeroMetricProps) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 px-4 py-4">
      <p className="text-xs uppercase tracking-[0.24em] text-white/55">{label}</p>
      <p className="mt-3 text-2xl font-semibold">{value}</p>
      <p className="mt-2 text-sm text-white/70">{detail}</p>
    </div>
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
  const [showReconcile, setShowReconcile] = useState(false);
  const [reconcileSaving, setReconcileSaving] = useState(false);
  const [reconcileForm, setReconcileForm] = useState({ product_id: '', counted_qty: 0, reason: '', notes: '' });
  const [showAdjust, setShowAdjust] = useState(false);
  const [adjustSaving, setAdjustSaving] = useState(false);
  const [adjustForm, setAdjustForm] = useState({ product_id: '', type: 'adjustment', quantity: 0, notes: '' });
  const limit = 25;

  const params = useMemo(
    () => ({
      skip: page * limit,
      limit,
      ...(search ? { search } : {}),
      ...(type ? { type } : {}),
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
    }),
    [page, limit, search, type, dateFrom, dateTo]
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
  const totalPages = data ? Math.max(1, Math.ceil(data.total / limit)) : 1;

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
      <section className="rounded-lg border border-border bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.16),_transparent_24%),linear-gradient(135deg,_rgba(8,17,31,1),_rgba(16,33,52,0.98)_48%,_rgba(19,52,34,0.96)_100%)] p-6 text-white shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm uppercase tracking-[0.3em] text-white/65">Stock Workspace</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold">
              <Boxes className="h-8 w-8" />
              Exceptions first
            </h1>
            <p className="mt-3 text-sm text-white/80">
              Lead with stock problems that affect selling and fulfillment. The ledger is still here, but it no longer gets the best seat in the room.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => openReconcile()}
              className="inline-flex min-h-12 items-center gap-2 rounded-md bg-primary px-5 py-3 font-semibold text-primary-foreground transition-opacity hover:opacity-90"
            >
              <ClipboardCheck className="h-4 w-4" />
              Reconcile stock
            </button>
            <button
              type="button"
              onClick={() => openAdjust()}
              className="inline-flex min-h-12 items-center gap-2 rounded-md border border-white/20 bg-white/10 px-5 py-3 font-semibold text-white transition-colors hover:bg-white/15"
            >
              <Plus className="h-4 w-4" />
              Quick adjustment
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-3 lg:grid-cols-4">
          <HeroMetric
            label="Product Alerts"
            value={String(productAlerts.length)}
            detail="POS and finished-goods issues requiring action"
          />
          <HeroMetric
            label="Critical Stockouts"
            value={String(criticalProductAlerts.length)}
            detail="Products already at zero stock"
          />
          <HeroMetric
            label="Near Reorder"
            value={String(nearReorderProducts.length)}
            detail="Products still sellable but nearing depletion"
          />
          <HeroMetric
            label="Material Signals"
            value={String(materialAlerts.length)}
            detail="Lower-priority material stock issues"
          />
        </div>
      </section>

      {showReconcile ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(event) => event.target === event.currentTarget && setShowReconcile(false)}
        >
          <div className="w-full max-w-lg rounded-md border border-border bg-card p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Stock reconciliation</h2>
              <button
                type="button"
                onClick={() => setShowReconcile(false)}
                className="rounded-md p-1 transition-colors hover:bg-accent"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Product</label>
                <select
                  value={reconcileForm.product_id}
                  onChange={(event) => setReconcileForm((form) => ({ ...form, product_id: event.target.value }))}
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
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

              <div>
                <label className="mb-1 block text-sm font-medium">Counted quantity</label>
                <input
                  type="number"
                  min="0"
                  value={reconcileForm.counted_qty}
                  onChange={(event) =>
                    setReconcileForm((form) => ({ ...form, counted_qty: Number(event.target.value) }))
                  }
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Reason</label>
                <input
                  value={reconcileForm.reason}
                  onChange={(event) => setReconcileForm((form) => ({ ...form, reason: event.target.value }))}
                  placeholder="Cycle count, shelf recount, received correction..."
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Notes</label>
                <textarea
                  value={reconcileForm.notes}
                  onChange={(event) => setReconcileForm((form) => ({ ...form, notes: event.target.value }))}
                  rows={3}
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={submitReconcile}
                disabled={reconcileSaving}
                className="flex-1 rounded-xl bg-primary py-2.5 font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {reconcileSaving ? 'Submitting...' : 'Submit Reconciliation'}
              </button>
              <button
                type="button"
                onClick={() => setShowReconcile(false)}
                className="rounded-xl border border-border px-4 py-2.5 transition-colors hover:bg-accent"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showAdjust ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(event) => event.target === event.currentTarget && setShowAdjust(false)}
        >
          <div className="w-full max-w-md rounded-md border border-border bg-card p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Quick stock adjustment</h2>
              <button
                type="button"
                onClick={() => setShowAdjust(false)}
                className="rounded-md p-1 transition-colors hover:bg-accent"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Product</label>
                <select
                  value={adjustForm.product_id}
                  onChange={(event) => setAdjustForm((form) => ({ ...form, product_id: event.target.value }))}
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
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

              <div>
                <label className="mb-1 block text-sm font-medium">Type</label>
                <select
                  value={adjustForm.type}
                  onChange={(event) => setAdjustForm((form) => ({ ...form, type: event.target.value }))}
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {TYPE_OPTIONS.filter((option) => option.value).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Quantity</label>
                <input
                  type="number"
                  value={adjustForm.quantity}
                  onChange={(event) => setAdjustForm((form) => ({ ...form, quantity: Number(event.target.value) }))}
                  placeholder="Positive to add, negative to remove"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Notes</label>
                <textarea
                  value={adjustForm.notes}
                  onChange={(event) => setAdjustForm((form) => ({ ...form, notes: event.target.value }))}
                  rows={3}
                  placeholder="Reason for adjustment"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={submitAdjust}
                disabled={adjustSaving}
                className="flex-1 rounded-xl bg-primary py-2.5 font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {adjustSaving ? 'Submitting...' : 'Submit Adjustment'}
              </button>
              <button
                type="button"
                onClick={() => setShowAdjust(false)}
                className="rounded-xl border border-border px-4 py-2.5 transition-colors hover:bg-accent"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

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
                              <span
                                className={cn(
                                  'rounded-full px-2.5 py-0.5 text-xs font-semibold',
                                  isCritical
                                    ? 'bg-destructive text-destructive-foreground'
                                    : 'bg-amber-100 text-amber-900'
                                )}
                              >
                                {isCritical ? 'Stockout' : 'Reorder risk'}
                              </span>
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">
                              {(alert.sku || 'No SKU')} • Stock {alert.current_stock} / Reorder {alert.reorder_point}
                            </p>
                          </div>

                          <div className="flex flex-wrap gap-2 text-sm">
                            <button
                              type="button"
                              onClick={() => openAdjust(alert.id)}
                              className="rounded-xl bg-primary px-3 py-2 font-semibold text-primary-foreground transition-opacity hover:opacity-90"
                            >
                              Adjust
                            </button>
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
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[transaction.type] || ''}`}>
                            {transaction.type}
                          </span>
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
        <div className="space-y-6">
          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <ScrollText className="h-5 w-5 text-muted-foreground" />
                  <h2 className="text-xl font-semibold">Inventory ledger</h2>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Full transaction history stays available for audit work and troubleshooting, but it is intentionally a secondary surface.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSurface('exceptions')}
                className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm font-semibold transition-colors hover:bg-accent"
              >
                Back to exceptions
              </button>
            </div>

            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-4">
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(0);
                }}
                placeholder="Search product name or SKU"
                className="rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <select
                value={type}
                onChange={(event) => {
                  setType(event.target.value);
                  setPage(0);
                }}
                className="rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <input
                type="date"
                value={dateFrom}
                onChange={(event) => {
                  setDateFrom(event.target.value);
                  setPage(0);
                }}
                className="rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <input
                type="date"
                value={dateTo}
                onChange={(event) => {
                  setDateTo(event.target.value);
                  setPage(0);
                }}
                className="rounded-xl border border-input bg-background px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </section>

          {isLoading ? (
            <SkeletonTable rows={8} cols={8} />
          ) : !items.length ? (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
              No inventory transactions found
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-sm">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="px-4 py-3 font-medium">Date</th>
                    <th className="px-4 py-3 font-medium">Product</th>
                    <th className="px-4 py-3 font-medium">SKU</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium text-right">Qty</th>
                    <th className="px-4 py-3 font-medium text-right">Unit Cost</th>
                    <th className="px-4 py-3 font-medium">Job</th>
                    <th className="px-4 py-3 font-medium">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((transaction) => (
                    <tr key={transaction.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                      <td className="px-4 py-3 text-xs">
                        {transaction.created_at ? new Date(transaction.created_at).toLocaleString() : '-'}
                      </td>
                      <td className="px-4 py-3">
                        {transaction.product_name ? (
                          <Link className="font-medium hover:underline" to={`/products/${transaction.product_id}`}>
                            {transaction.product_name}
                          </Link>
                        ) : (
                          transaction.product_id
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{transaction.product_sku || '-'}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[transaction.type] || ''}`}>
                          {transaction.type}
                        </span>
                      </td>
                      <td
                        className={cn(
                          'px-4 py-3 text-right font-medium',
                          transaction.quantity > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                        )}
                      >
                        {transaction.quantity > 0 ? '+' : ''}
                        {transaction.quantity}
                      </td>
                      <td className="px-4 py-3 text-right">{formatCurrency(transaction.unit_cost)}</td>
                      <td className="px-4 py-3 font-mono text-xs">{transaction.job_id || '-'}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{transaction.notes || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex items-center justify-between text-sm">
            <p className="text-muted-foreground">
              Page {page + 1} of {totalPages}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(0, current - 1))}
                disabled={page === 0}
                className="rounded-xl border border-border px-3 py-2 transition-colors hover:bg-accent disabled:opacity-50"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((current) => (current + 1 < totalPages ? current + 1 : current))}
                disabled={page + 1 >= totalPages}
                className="rounded-xl border border-border px-3 py-2 transition-colors hover:bg-accent disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="sr-only" aria-live="polite">
        Stock surface: {surface}
      </div>
    </div>
  );
}
