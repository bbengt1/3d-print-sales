import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Pencil, Plus, Archive, ArchiveRestore, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Label } from '@/components/ui/Label';
import { SkeletonTable } from '@/components/ui/Skeleton';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';
import type { Product, PaginatedTransactions } from '@/types';

const TXN_TYPES = [
  { value: 'adjustment', label: 'Adjustment' },
  { value: 'production', label: 'Production' },
  { value: 'sale', label: 'Sale' },
  { value: 'return', label: 'Return' },
  { value: 'waste', label: 'Waste' },
];

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: product, isLoading: productLoading } = useQuery<Product>({
    queryKey: ['product', id],
    queryFn: () => api.get(`/products/${id}`).then((r) => r.data),
  });

  const { data: transactions, isLoading: txnLoading } = useQuery<PaginatedTransactions>({
    queryKey: ['transactions', id],
    queryFn: () => api.get('/inventory/transactions', { params: { product_id: id, limit: 50 } }).then((r) => r.data),
  });

  const [showAdjust, setShowAdjust] = useState(false);
  const [showZeroStock, setShowZeroStock] = useState(false);
  const [adjForm, setAdjForm] = useState({ type: 'adjustment', quantity: 0, notes: '' });
  const [zeroReason, setZeroReason] = useState('');
  const [saving, setSaving] = useState(false);

  const submitAdjustment = async () => {
    if (adjForm.quantity === 0) { toast.error('Quantity cannot be 0'); return; }
    setSaving(true);
    try {
      await api.post('/inventory/transactions', {
        product_id: id,
        type: adjForm.type,
        quantity: adjForm.quantity,
        unit_cost: product?.unit_cost || 0,
        notes: adjForm.notes || null,
      });
      toast.success('Stock adjusted');
      queryClient.invalidateQueries({ queryKey: ['product', id] });
      queryClient.invalidateQueries({ queryKey: ['transactions', id] });
      setShowAdjust(false);
      setAdjForm({ type: 'adjustment', quantity: 0, notes: '' });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to adjust stock');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async () => {
    const confirmed = window.confirm(
      currentProduct.is_active
        ? `Archive ${currentProduct.name}?\n\nThis keeps historical records and inventory history, but removes the product from active use.`
        : `Restore ${currentProduct.name} to active products?`
    );

    if (!confirmed) return;

    setSaving(true);
    try {
      if (currentProduct.is_active) {
        await api.delete(`/products/${currentProduct.id}`);
        toast.success(`${currentProduct.name} archived`);
      } else {
        await api.put(`/products/${currentProduct.id}`, { is_active: true });
        toast.success(`${currentProduct.name} restored`);
      }
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product', id] });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update product status');
    } finally {
      setSaving(false);
    }
  };

  const submitZeroStock = async () => {
    if (currentProduct.stock_qty === 0) {
      toast.error('Product stock is already 0');
      return;
    }
    if (!zeroReason.trim()) {
      toast.error('Reason is required');
      return;
    }

    setSaving(true);
    try {
      await api.post('/inventory/transactions', {
        product_id: currentProduct.id,
        type: 'adjustment',
        quantity: currentProduct.stock_qty * -1,
        unit_cost: currentProduct.unit_cost || 0,
        notes: zeroReason.trim(),
      });
      toast.success('Product stock set to 0');
      setShowZeroStock(false);
      setZeroReason('');
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product', id] });
      queryClient.invalidateQueries({ queryKey: ['transactions', id] });
      queryClient.invalidateQueries({ queryKey: ['inventory-transactions'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-alerts'] });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to set stock to 0');
    } finally {
      setSaving(false);
    }
  };

  if (productLoading) return <SkeletonTable rows={3} cols={4} />;
  if (!product) return <p className="text-center py-16 text-muted-foreground">Product not found</p>;

  const currentProduct = product;

  return (
    <div className="max-w-4xl mx-auto">
      <Link to="/product-studio" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to Products
      </Link>

      {/* Product Info */}
      <div className="bg-card border border-border rounded-lg p-6 mb-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-2xl font-semibold">{currentProduct.name}</h1>
            <p className="text-sm text-muted-foreground font-mono">{currentProduct.sku}</p>
            {currentProduct.upc && <p className="text-xs text-muted-foreground mt-1">UPC: {currentProduct.upc}</p>}
            {!currentProduct.is_active && <p className="text-sm text-muted-foreground mt-2">This product is archived. Historical records and inventory history are preserved.</p>}
          </div>
          <div className="flex flex-col items-end gap-2">
            <StatusBadge tone={currentProduct.is_active ? 'success' : 'warning'}>
              {currentProduct.is_active ? 'Active' : 'Archived'}
            </StatusBadge>
            <Link
              to={`/product-studio/products/${currentProduct.id}/edit`}
              className="inline-flex items-center gap-2 px-3 py-2 border border-border rounded-md hover:bg-accent no-underline text-foreground"
            >
              <Pencil className="w-4 h-4" />
              Open Editor
            </Link>
            <button
              onClick={toggleActive}
              disabled={saving}
              className="inline-flex items-center gap-2 px-3 py-2 border border-border rounded-md hover:bg-accent disabled:opacity-50 cursor-pointer"
            >
              {currentProduct.is_active ? <Archive className="w-4 h-4" /> : <ArchiveRestore className="w-4 h-4" />}
              {currentProduct.is_active ? 'Archive Product' : 'Restore Product'}
            </button>
          </div>
        </div>
        {product.description && <p className="text-sm text-muted-foreground mb-4">{product.description}</p>}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Unit Price</p>
            <p className="text-lg font-semibold">{formatCurrency(product.unit_price)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Unit Cost</p>
            <p className="text-lg font-semibold">{formatCurrency(product.unit_cost)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Stock on Hand</p>
            <p className={`text-lg font-semibold ${product.stock_qty <= product.reorder_point ? 'text-amber-600 dark:text-amber-400' : ''}`}>
              {product.stock_qty}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Reorder Point</p>
            <p className="text-lg font-semibold">{product.reorder_point}</p>
          </div>
        </div>
        {Number(product.unit_price) > 0 && Number(product.unit_cost) > 0 && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-sm text-muted-foreground">
              Margin: {((1 - Number(product.unit_cost) / Number(product.unit_price)) * 100).toFixed(1)}%
              &nbsp;|&nbsp; Inventory Value: {formatCurrency(Number(product.unit_cost) * product.stock_qty)}
            </p>
          </div>
        )}
      </div>

      {/* Adjust Stock */}
      <div className="flex items-center justify-between mb-4 gap-3">
        <h2 className="text-xl font-semibold">Transaction History</h2>
        <div className="flex gap-2">
          <button
            onClick={() => {
              if (currentProduct.stock_qty === 0) {
                toast.error('Product stock is already 0');
                return;
              }
              setZeroReason('');
              setShowZeroStock(true);
            }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium border border-border hover:bg-accent transition-colors cursor-pointer"
          >
            <RotateCcw className="w-4 h-4" /> Set Stock to 0
          </button>
          <Button onClick={() => setShowAdjust(true)}>
            <Plus className="h-4 w-4" /> Adjust Stock
          </Button>
        </div>
      </div>

      {/* Zero Stock Modal */}
      <Dialog open={showZeroStock} onOpenChange={(open) => !open && setShowZeroStock(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Set stock to 0</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="rounded-md bg-accent/40 p-4 text-sm space-y-2">
              <div className="flex items-center justify-between gap-4">
                <span className="text-muted-foreground">Current stock</span>
                <span className="font-semibold">{currentProduct.stock_qty}</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-muted-foreground">Resulting stock</span>
                <span className="font-semibold">0</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-muted-foreground">Inventory adjustment</span>
                <span className="font-semibold text-destructive">-{currentProduct.stock_qty}</span>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              This creates an inventory adjustment record and preserves audit history. A reason is required.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="zero-stock-reason">Reason</Label>
              <Textarea
                id="zero-stock-reason"
                value={zeroReason}
                onChange={(e) => setZeroReason(e.target.value)}
                rows={3}
                placeholder="Why is stock being reset to zero?"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowZeroStock(false)}>Cancel</Button>
            <Button onClick={submitZeroStock} disabled={saving}>
              {saving ? 'Submitting…' : 'Set stock to 0'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Adjustment Modal */}
      <Dialog open={showAdjust} onOpenChange={(open) => !open && setShowAdjust(false)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Adjust stock</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="adjust-type-detail">Type</Label>
              <select
                id="adjust-type-detail"
                value={adjForm.type}
                onChange={(e) => setAdjForm({ ...adjForm, type: e.target.value })}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {TXN_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="adjust-qty-detail">Quantity</Label>
              <Input id="adjust-qty-detail" type="number" value={adjForm.quantity} onChange={(e) => setAdjForm({ ...adjForm, quantity: Number(e.target.value) })} placeholder="Positive to add, negative to remove" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="adjust-notes-detail">Notes</Label>
              <Input id="adjust-notes-detail" value={adjForm.notes} onChange={(e) => setAdjForm({ ...adjForm, notes: e.target.value })} placeholder="Optional" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdjust(false)}>Cancel</Button>
            <Button onClick={submitAdjustment} disabled={saving}>{saving ? 'Saving…' : 'Submit'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Transaction History */}
      {txnLoading ? (
        <SkeletonTable rows={5} cols={5} />
      ) : !transactions?.items?.length ? (
        <div className="bg-card border border-border rounded-lg p-8 text-center text-muted-foreground">
          No transactions yet
        </div>
      ) : (
        <div className="overflow-x-auto bg-card border border-border rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium text-right">Qty</th>
                <th className="px-4 py-3 font-medium text-right">Unit Cost</th>
                <th className="px-4 py-3 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody>
              {transactions.items.map((t) => (
                <tr key={t.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 text-xs">{t.created_at ? new Date(t.created_at).toLocaleString() : '-'}</td>
                  <td className="px-4 py-3">
                    <StatusBadge tone={defaultStatusTone(t.type)}>{t.type}</StatusBadge>
                  </td>
                  <td className={`px-4 py-3 text-right font-medium ${t.quantity > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>
                    {t.quantity > 0 ? '+' : ''}{t.quantity}
                  </td>
                  <td className="px-4 py-3 text-right">{formatCurrency(t.unit_cost)}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{t.notes || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
