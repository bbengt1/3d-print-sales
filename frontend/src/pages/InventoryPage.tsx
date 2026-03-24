import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import { SkeletonTable } from '@/components/ui/Skeleton';
import type { InventoryAlert, InventoryReconcileResponse, PaginatedProducts, PaginatedTransactions } from '@/types';

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'production', label: 'Production' },
  { value: 'sale', label: 'Sale' },
  { value: 'adjustment', label: 'Adjustment' },
  { value: 'return', label: 'Return' },
  { value: 'waste', label: 'Waste' },
];

const TYPE_COLORS: Record<string, string> = {
  production: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  sale: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  adjustment: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  return: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
  waste: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

export default function InventoryPage() {
  const queryClient = useQueryClient();
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

  const params = useMemo(() => ({
    skip: page * limit,
    limit,
    ...(search ? { search } : {}),
    ...(type ? { type } : {}),
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
  }), [page, limit, search, type, dateFrom, dateTo]);

  const { data, isLoading } = useQuery<PaginatedTransactions>({
    queryKey: ['inventory-transactions', params],
    queryFn: () => api.get('/inventory/transactions', { params }).then((r) => r.data),
  });

  const { data: alerts } = useQuery<InventoryAlert[]>({
    queryKey: ['inventory-alerts'],
    queryFn: () => api.get('/inventory/alerts').then((r) => r.data),
  });

  const { data: productsData } = useQuery<PaginatedProducts>({
    queryKey: ['products', 'inventory-reconcile'],
    queryFn: () => api.get('/products?is_active=true&limit=200').then((r) => r.data),
  });

  const items = data?.items || [];
  const selectedProduct = productsData?.items.find((product) => product.id === reconcileForm.product_id) || null;
  const adjustProduct = productsData?.items.find((product) => product.id === adjustForm.product_id) || null;
  const variance = selectedProduct ? reconcileForm.counted_qty - selectedProduct.stock_qty : 0;

  const openReconcile = (productId?: string) => {
    setReconcileForm({ product_id: productId || '', counted_qty: 0, reason: '', notes: '' });
    setShowReconcile(true);
  };

  const submitReconcile = async () => {
    if (!reconcileForm.product_id) { toast.error('Select a product'); return; }
    if (!reconcileForm.reason.trim()) { toast.error('Reason is required'); return; }
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

  const openAdjust = (productId?: string) => {
    setAdjustForm({ product_id: productId || '', type: 'adjustment', quantity: 0, notes: '' });
    setShowAdjust(true);
  };

  const submitAdjust = async () => {
    if (!adjustForm.product_id) { toast.error('Select a product'); return; }
    if (adjustForm.quantity === 0) { toast.error('Quantity cannot be 0'); return; }
    if (adjustForm.type === 'adjustment' && !adjustForm.notes.trim()) { toast.error('Adjustment notes are required'); return; }
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
  const totalPages = data ? Math.max(1, Math.ceil(data.total / limit)) : 1;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Inventory</h1>
          <p className="text-sm text-muted-foreground mt-1">Global stock ledger, recent movements, and low-stock operational view.</p>
        </div>
        <button onClick={() => openReconcile()} className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90">
          Reconcile Stock
        </button>
      </div>

      {showReconcile && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={(e) => e.target === e.currentTarget && setShowReconcile(false)}>
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-lg">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Stock Reconciliation</h2>
              <button type="button" onClick={() => setShowReconcile(false)} className="p-1 hover:bg-accent rounded-md"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Product</label>
                <select value={reconcileForm.product_id} onChange={(e) => setReconcileForm((f) => ({ ...f, product_id: e.target.value }))} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring">
                  <option value="">Select product...</option>
                  {productsData?.items.map((product) => (
                    <option key={product.id} value={product.id}>{product.name} ({product.sku})</option>
                  ))}
                </select>
              </div>
              {selectedProduct && (
                <div className="grid grid-cols-2 gap-4 text-sm bg-accent/40 rounded-md p-3">
                  <div>
                    <p className="text-muted-foreground">Current system qty</p>
                    <p className="text-lg font-semibold">{selectedProduct.stock_qty}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Variance</p>
                    <p className={`text-lg font-semibold ${variance > 0 ? 'text-green-600 dark:text-green-400' : variance < 0 ? 'text-red-600 dark:text-red-400' : ''}`}>{variance > 0 ? '+' : ''}{variance}</p>
                  </div>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium mb-1">Counted quantity</label>
                <input type="number" min="0" value={reconcileForm.counted_qty} onChange={(e) => setReconcileForm((f) => ({ ...f, counted_qty: Number(e.target.value) }))} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Reason</label>
                <input value={reconcileForm.reason} onChange={(e) => setReconcileForm((f) => ({ ...f, reason: e.target.value }))} placeholder="Cycle count, shelf recount, received correction..." className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Notes</label>
                <textarea value={reconcileForm.notes} onChange={(e) => setReconcileForm((f) => ({ ...f, notes: e.target.value }))} rows={3} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={submitReconcile} disabled={reconcileSaving} className="flex-1 bg-primary text-primary-foreground py-2 rounded-md font-medium hover:opacity-90 disabled:opacity-50">{reconcileSaving ? 'Submitting...' : 'Submit Reconciliation'}</button>
              <button onClick={() => setShowReconcile(false)} className="px-4 py-2 border border-border rounded-md hover:bg-accent">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {showAdjust && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={(e) => e.target === e.currentTarget && setShowAdjust(false)}>
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Quick Stock Adjustment</h2>
              <button type="button" onClick={() => setShowAdjust(false)} className="p-1 hover:bg-accent rounded-md"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Product</label>
                <select value={adjustForm.product_id} onChange={(e) => setAdjustForm((f) => ({ ...f, product_id: e.target.value }))} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring">
                  <option value="">Select product...</option>
                  {productsData?.items.map((product) => (
                    <option key={product.id} value={product.id}>{product.name} ({product.sku})</option>
                  ))}
                </select>
              </div>
              {adjustProduct && (
                <div className="text-sm bg-accent/40 rounded-md p-3">
                  <p className="text-muted-foreground">Current stock</p>
                  <p className="text-lg font-semibold">{adjustProduct.stock_qty}</p>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium mb-1">Type</label>
                <select value={adjustForm.type} onChange={(e) => setAdjustForm((f) => ({ ...f, type: e.target.value }))} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring">
                  {TYPE_OPTIONS.filter((option) => option.value).map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Quantity</label>
                <input type="number" value={adjustForm.quantity} onChange={(e) => setAdjustForm((f) => ({ ...f, quantity: Number(e.target.value) }))} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" placeholder="Positive to add, negative to remove" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Notes</label>
                <textarea value={adjustForm.notes} onChange={(e) => setAdjustForm((f) => ({ ...f, notes: e.target.value }))} rows={3} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" placeholder="Reason for adjustment" />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={submitAdjust} disabled={adjustSaving} className="flex-1 bg-primary text-primary-foreground py-2 rounded-md font-medium hover:opacity-90 disabled:opacity-50">{adjustSaving ? 'Submitting...' : 'Submit Adjustment'}</button>
              <button onClick={() => setShowAdjust(false)} className="px-4 py-2 border border-border rounded-md hover:bg-accent">Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-card border border-border rounded-lg p-4 grid grid-cols-1 md:grid-cols-4 gap-4">
        <input
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          placeholder="Search product name or SKU"
          className="px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <select value={type} onChange={(e) => { setType(e.target.value); setPage(0); }} className="px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring">
          {TYPE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(0); }} className="px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
        <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(0); }} className="px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
      </div>

      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Low-stock alerts</h2>
          <span className="text-xs text-muted-foreground">Quick links only for now; reconcile flow comes next.</span>
        </div>
        {!alerts?.length ? (
          <p className="text-sm text-muted-foreground">No low-stock alerts.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {alerts.map((alert) => (
              <div key={`${alert.type}-${alert.id}`} className="border border-border rounded-md p-3 flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium">{alert.name}</p>
                  <p className="text-xs text-muted-foreground">{alert.type === 'product' ? (alert.sku || 'No SKU') : 'Material'} · Stock {alert.current_stock} / Reorder {alert.reorder_point}</p>
                </div>
                <div className="flex gap-2 text-sm">
                  {alert.type === 'product' ? (
                    <>
                      <button type="button" onClick={() => openAdjust(alert.id)} className="text-primary hover:underline">Adjust</button>
                      <button type="button" onClick={() => openReconcile(alert.id)} className="text-primary hover:underline">Reconcile</button>
                      <Link className="text-primary hover:underline" to={`/products/${alert.id}`}>View product</Link>
                    </>
                  ) : (
                    <Link className="text-primary hover:underline" to="/materials">View materials</Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {isLoading ? (
        <SkeletonTable rows={8} cols={8} />
      ) : !items.length ? (
        <div className="bg-card border border-border rounded-lg p-8 text-center text-muted-foreground">No inventory transactions found</div>
      ) : (
        <div className="overflow-x-auto bg-card border border-border rounded-lg">
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
              {items.map((t) => (
                <tr key={t.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 text-xs">{t.created_at ? new Date(t.created_at).toLocaleString() : '-'}</td>
                  <td className="px-4 py-3">
                    {t.product_name ? <Link className="font-medium hover:underline" to={`/products/${t.product_id}`}>{t.product_name}</Link> : t.product_id}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{t.product_sku || '-'}</td>
                  <td className="px-4 py-3"><span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[t.type] || ''}`}>{t.type}</span></td>
                  <td className={`px-4 py-3 text-right font-medium ${t.quantity > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{t.quantity > 0 ? '+' : ''}{t.quantity}</td>
                  <td className="px-4 py-3 text-right">{formatCurrency(t.unit_cost)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{t.job_id || '-'}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{t.notes || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm">
        <p className="text-muted-foreground">Page {page + 1} of {totalPages}</p>
        <div className="flex gap-2">
          <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} className="px-3 py-2 border border-border rounded-md disabled:opacity-50 hover:bg-accent">Previous</button>
          <button onClick={() => setPage((p) => (p + 1 < totalPages ? p + 1 : p))} disabled={page + 1 >= totalPages} className="px-3 py-2 border border-border rounded-md disabled:opacity-50 hover:bg-accent">Next</button>
        </div>
      </div>
    </div>
  );
}
