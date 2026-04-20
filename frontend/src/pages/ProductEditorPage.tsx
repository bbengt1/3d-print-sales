import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BadgeDollarSign,
  Boxes,
  ReceiptText,
  Save,
  ScanBarcode,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import EmptyState from '@/components/ui/EmptyState';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import PageHeader from '@/components/layout/PageHeader';
import { cn, formatCurrency } from '@/lib/utils';
import type { InventoryTransaction, Material, PaginatedTransactions, Product } from '@/types';

const emptyForm = {
  name: '',
  description: '',
  material_id: '',
  upc: '',
  unit_price: 0,
  reorder_point: 5,
};

function readinessTone(value: 'ready' | 'warning' | 'draft') {
  if (value === 'ready') return 'bg-emerald-50 text-emerald-900 border-emerald-300/60';
  if (value === 'warning') return 'bg-amber-50 text-amber-900 border-amber-300/60';
  return 'bg-slate-100 text-slate-800 border-slate-300/60';
}

export default function ProductEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isCreate = !id;
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [form, setForm] = useState(emptyForm);
  const [initialized, setInitialized] = useState(false);

  const { data: materials = [], isLoading: materialsLoading } = useQuery<Material[]>({
    queryKey: ['materials', 'active'],
    queryFn: () => api.get('/materials?active=true').then((r) => r.data),
  });

  const { data: product, isLoading: productLoading } = useQuery<Product>({
    queryKey: ['product', id],
    enabled: Boolean(id),
    queryFn: () => api.get(`/products/${id}`).then((r) => r.data),
  });

  const { data: transactionsData, isLoading: transactionsLoading } = useQuery<PaginatedTransactions>({
    queryKey: ['transactions', id, 'editor'],
    enabled: Boolean(id),
    queryFn: () =>
      api.get('/inventory/transactions', { params: { product_id: id, limit: 6 } }).then((r) => r.data),
  });

  if (product && !initialized) {
    setForm({
      name: product.name,
      description: product.description || '',
      material_id: product.material_id,
      upc: product.upc || '',
      unit_price: Number(product.unit_price),
      reorder_point: product.reorder_point,
    });
    setInitialized(true);
  }

  const selectedMaterial = materials.find((material) => material.id === form.material_id) || null;
  const unitCost = product?.unit_cost ?? 0;
  const stockQty = product?.stock_qty ?? 0;
  const marginDollars = Number(form.unit_price || 0) - Number(unitCost || 0);
  const marginPct = Number(form.unit_price || 0) > 0 ? (marginDollars / Number(form.unit_price || 1)) * 100 : 0;
  const inventoryValue = stockQty * Number(unitCost || 0);
  const recentTransactions = transactionsData?.items || [];

  const identityReadiness = useMemo(() => {
    if (form.name.trim() && form.material_id && Number(form.unit_price) > 0) return 'ready';
    if (form.name.trim() || form.material_id || Number(form.unit_price) > 0) return 'warning';
    return 'draft';
  }, [form.material_id, form.name, form.unit_price]);

  const barcodeReadiness = form.upc.trim() ? 'ready' : 'warning';
  const stockReadiness =
    isCreate || stockQty > form.reorder_point ? 'ready' : stockQty > 0 ? 'warning' : 'draft';

  const validate = () => {
    const nextErrors: Record<string, string> = {};
    if (!form.name.trim()) nextErrors.name = 'Name is required';
    if (!form.material_id) nextErrors.material_id = 'Select a material';
    if (Number(form.unit_price) < 0) nextErrors.unit_price = 'Price cannot be negative';
    if (Number(form.reorder_point) < 0) nextErrors.reorder_point = 'Reorder point cannot be negative';
    setFormErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const save = async () => {
    if (!validate()) return;

    setSaving(true);
    try {
      const payload = {
        ...form,
        description: form.description.trim() || null,
        upc: form.upc.trim() || null,
        unit_price: Number(form.unit_price) || 0,
        reorder_point: Number(form.reorder_point) || 0,
      };

      if (isCreate) {
        const response = await api.post<Product>('/products', payload);
        toast.success('Product created');
        queryClient.invalidateQueries({ queryKey: ['products'] });
        navigate(`/product-studio/products/${response.data.id}/edit`);
      } else {
        await api.put(`/products/${id}`, payload);
        toast.success('Product updated');
        queryClient.invalidateQueries({ queryKey: ['products'] });
        queryClient.invalidateQueries({ queryKey: ['product', id] });
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save product');
    } finally {
      setSaving(false);
    }
  };

  if ((productLoading && !isCreate) || materialsLoading) {
    return <SkeletonTable rows={6} cols={5} />;
  }

  if (!isCreate && !product) {
    return <p className="py-16 text-center text-muted-foreground">Product not found</p>;
  }

  const inputClass = (field: string) =>
    `w-full rounded-md border px-4 py-3 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring ${
      formErrors[field] ? 'border-destructive' : 'border-input'
    }`;

  return (
    <div className="space-y-6">
      <PageHeader
        title={isCreate ? 'New product' : product?.name || 'Product editor'}
        description={isCreate ? 'Draft' : product?.is_active ? 'Active' : 'Archived'}
        actions={
          <>
            <Link
              to="/product-studio"
              className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium no-underline hover:bg-muted transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to catalog
            </Link>
            {!isCreate ? (
              <Link
                to={`/product-studio/products/${id}`}
                className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium no-underline hover:bg-muted transition-colors"
              >
                View record
                <ArrowRight className="h-4 w-4" />
              </Link>
            ) : null}
          </>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
        <section className="space-y-6">
          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <ReceiptText className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-xl font-semibold">Identity and sellable details</h2>
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <div className="lg:col-span-2">
                <label className="mb-2 block text-sm font-medium">Product name</label>
                <input
                  value={form.name}
                  onChange={(event) => {
                    setForm((current) => ({ ...current, name: event.target.value }));
                    setFormErrors((current) => ({ ...current, name: '' }));
                  }}
                  className={inputClass('name')}
                  placeholder="Desk Dragon, Tool Holder, Display Plaque..."
                />
                {formErrors.name ? <p className="mt-1 text-xs text-destructive">{formErrors.name}</p> : null}
              </div>

              <div className="lg:col-span-2">
                <label className="mb-2 block text-sm font-medium">Description</label>
                <textarea
                  value={form.description}
                  onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                  rows={4}
                  className={inputClass('description')}
                  placeholder="Short operator-facing or storefront-facing summary."
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">SKU</label>
                <div className="rounded-md border border-border bg-background px-4 py-3 text-sm">
                  {product?.sku || 'Generated after first save'}
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">UPC / barcode</label>
                <div className="relative">
                  <ScanBarcode className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={form.upc}
                    onChange={(event) => setForm((current) => ({ ...current, upc: event.target.value }))}
                    className={`${inputClass('upc')} pl-10`}
                    placeholder="012345678901"
                  />
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">Material</label>
                <select
                  value={form.material_id}
                  onChange={(event) => {
                    setForm((current) => ({ ...current, material_id: event.target.value }));
                    setFormErrors((current) => ({ ...current, material_id: '' }));
                  }}
                  className={inputClass('material_id')}
                >
                  <option value="">Select material...</option>
                  {materials.map((material) => (
                    <option key={material.id} value={material.id}>
                      {material.name} ({material.brand})
                    </option>
                  ))}
                </select>
                {formErrors.material_id ? <p className="mt-1 text-xs text-destructive">{formErrors.material_id}</p> : null}
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">Unit price</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.unit_price}
                  onChange={(event) => setForm((current) => ({ ...current, unit_price: Number(event.target.value) }))}
                  className={inputClass('unit_price')}
                />
                {formErrors.unit_price ? <p className="mt-1 text-xs text-destructive">{formErrors.unit_price}</p> : null}
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">Reorder point</label>
                <input
                  type="number"
                  min="0"
                  value={form.reorder_point}
                  onChange={(event) => setForm((current) => ({ ...current, reorder_point: Number(event.target.value) }))}
                  className={inputClass('reorder_point')}
                />
                {formErrors.reorder_point ? <p className="mt-1 text-xs text-destructive">{formErrors.reorder_point}</p> : null}
              </div>
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <Button
                type="button"
                onClick={save}
                disabled={saving}
                size="lg"
                className="min-h-12 font-semibold"
              >
                <Save className="h-4 w-4" />
                {saving ? 'Saving...' : isCreate ? 'Create product' : 'Save changes'}
              </Button>
              {!isCreate ? (
                <Link
                  to={`/product-studio/products/${id}`}
                  className="inline-flex min-h-12 items-center gap-2 rounded-md border border-border px-5 py-3 font-semibold text-foreground no-underline transition-colors hover:bg-accent"
                >
                  Open detail record
                </Link>
              ) : null}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <Boxes className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-xl font-semibold">Stock and activity context</h2>
            </div>
            {isCreate ? (
              <EmptyState
                icon="products"
                title="Stock activity starts after creation"
                description="Save the product first to start tracking stock movement, adjustments, and production receipts."
                className="py-10"
              />
            ) : transactionsLoading ? (
              <SkeletonTable rows={3} cols={4} />
            ) : !recentTransactions.length ? (
              <p className="mt-4 text-sm text-muted-foreground">No stock activity recorded yet for this product.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {recentTransactions.map((transaction: InventoryTransaction) => (
                  <div key={transaction.id} className="rounded-md border border-border bg-background/80 px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium capitalize">{transaction.type}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {transaction.created_at ? new Date(transaction.created_at).toLocaleString() : '-'}
                        </p>
                      </div>
                      <p
                        className={cn(
                          'font-semibold',
                          transaction.quantity > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                        )}
                      >
                        {transaction.quantity > 0 ? '+' : ''}
                        {transaction.quantity}
                      </p>
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">{transaction.notes || 'No notes recorded'}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <BadgeDollarSign className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-xl font-semibold">Readiness and margin</h2>
            </div>

            <div className="mt-4 space-y-3">
              <div className={cn('rounded-md border px-4 py-3', readinessTone(identityReadiness))}>
                <p className="font-semibold">Identity</p>
                <p className="mt-1 text-sm">
                  {identityReadiness === 'ready'
                    ? 'Name, material, and price are present.'
                    : identityReadiness === 'warning'
                      ? 'The product has partial setup but still needs key sellable fields.'
                      : 'Start with the basic product identity and pricing fields.'}
                </p>
              </div>

              <div className={cn('rounded-md border px-4 py-3', readinessTone(barcodeReadiness))}>
                <p className="font-semibold">POS readiness</p>
                <p className="mt-1 text-sm">
                  {barcodeReadiness === 'ready'
                    ? 'UPC present. This product can participate in barcode-driven POS flow.'
                    : 'No UPC yet. Product is still sellable, but manual lookup will be required at the register.'}
                </p>
              </div>

              <div className={cn('rounded-md border px-4 py-3', readinessTone(stockReadiness))}>
                <p className="font-semibold">Stock policy</p>
                <p className="mt-1 text-sm">
                  {isCreate
                    ? 'Stock starts after creation. Reorder policy will apply once transactions begin.'
                    : stockReadiness === 'ready'
                      ? 'Current stock is above the reorder threshold.'
                      : stockReadiness === 'warning'
                        ? 'Current stock is near the reorder point.'
                        : 'Current stock is at or below zero and needs attention.'}
                </p>
              </div>
            </div>

            <div className="mt-5 space-y-3 rounded-lg bg-background p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Unit price</span>
                <span>{formatCurrency(Number(form.unit_price || 0))}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Current unit cost</span>
                <span>{formatCurrency(Number(unitCost || 0))}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Margin dollars</span>
                <span className={cn(marginDollars >= 0 ? 'text-emerald-700' : 'text-red-600')}>
                  {formatCurrency(marginDollars)}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Margin percent</span>
                <span className={cn(marginPct >= 0 ? 'text-emerald-700' : 'text-red-600')}>
                  {Number.isFinite(marginPct) ? `${marginPct.toFixed(1)}%` : '0.0%'}
                </span>
              </div>
              <div className="flex items-center justify-between border-t border-border pt-3 text-sm">
                <span className="text-muted-foreground">Inventory value</span>
                <span>{formatCurrency(inventoryValue)}</span>
              </div>
            </div>

            {marginDollars < 0 ? (
              <div className="mt-4 rounded-md border border-destructive/35 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <p>This price is below the current unit cost.</p>
                </div>
              </div>
            ) : null}
          </section>

          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <h2 className="text-xl font-semibold">Material context</h2>
            {selectedMaterial ? (
              <div className="mt-4 space-y-3 text-sm">
                <div className="rounded-md bg-background px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Material</p>
                  <p className="mt-2 font-semibold">{selectedMaterial.name}</p>
                  <p className="mt-1 text-muted-foreground">{selectedMaterial.brand}</p>
                </div>
                <div className="rounded-md bg-background px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Cost per gram</p>
                  <p className="mt-2 font-semibold">${Number(selectedMaterial.cost_per_g).toFixed(4)}</p>
                </div>
                <div className="rounded-md bg-background px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Material stock</p>
                  <p className="mt-2 font-semibold">{selectedMaterial.spools_in_stock} spools</p>
                  <p className="mt-1 text-muted-foreground">Reorder at {selectedMaterial.reorder_point}</p>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">Select a material to see cost and stock context.</p>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
