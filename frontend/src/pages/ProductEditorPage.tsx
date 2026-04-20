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
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Label } from '@/components/ui/Label';
import { Callout, type CalloutTone } from '@/components/ui/Callout';
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

function readinessTone(value: 'ready' | 'warning' | 'draft'): CalloutTone {
  if (value === 'ready') return 'success';
  if (value === 'warning') return 'warning';
  return 'neutral';
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

  const selectClass = (field: string) =>
    `flex h-9 w-full rounded-md border bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring ${
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
              <div className="lg:col-span-2 space-y-1.5">
                <Label htmlFor="product-name">Product name *</Label>
                <Input
                  id="product-name"
                  value={form.name}
                  onChange={(event) => {
                    setForm((current) => ({ ...current, name: event.target.value }));
                    setFormErrors((current) => ({ ...current, name: '' }));
                  }}
                  invalid={Boolean(formErrors.name)}
                  placeholder="Desk Dragon, Tool Holder, Display Plaque..."
                />
                {formErrors.name ? <p className="text-xs text-destructive">{formErrors.name}</p> : null}
              </div>

              <div className="lg:col-span-2 space-y-1.5">
                <Label htmlFor="product-description">Description</Label>
                <Textarea
                  id="product-description"
                  value={form.description}
                  onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                  rows={4}
                  placeholder="Short operator-facing or storefront-facing summary."
                />
              </div>

              <div className="space-y-1.5">
                <Label>SKU</Label>
                <div className="rounded-md border border-border bg-background px-4 py-3 text-sm">
                  {product?.sku || 'Generated after first save'}
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="product-upc">UPC / barcode</Label>
                <div className="relative">
                  <ScanBarcode className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="product-upc"
                    value={form.upc}
                    onChange={(event) => setForm((current) => ({ ...current, upc: event.target.value }))}
                    className="pl-9"
                    placeholder="012345678901"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="product-material">Material *</Label>
                <select
                  id="product-material"
                  value={form.material_id}
                  onChange={(event) => {
                    setForm((current) => ({ ...current, material_id: event.target.value }));
                    setFormErrors((current) => ({ ...current, material_id: '' }));
                  }}
                  className={selectClass('material_id')}
                >
                  <option value="">Select material...</option>
                  {materials.map((material) => (
                    <option key={material.id} value={material.id}>
                      {material.name} ({material.brand})
                    </option>
                  ))}
                </select>
                {formErrors.material_id ? <p className="text-xs text-destructive">{formErrors.material_id}</p> : null}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="product-unit-price">Unit price</Label>
                <Input
                  id="product-unit-price"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.unit_price}
                  onChange={(event) => setForm((current) => ({ ...current, unit_price: Number(event.target.value) }))}
                  invalid={Boolean(formErrors.unit_price)}
                />
                {formErrors.unit_price ? <p className="text-xs text-destructive">{formErrors.unit_price}</p> : null}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="product-reorder">Reorder point</Label>
                <Input
                  id="product-reorder"
                  type="number"
                  min="0"
                  value={form.reorder_point}
                  onChange={(event) => setForm((current) => ({ ...current, reorder_point: Number(event.target.value) }))}
                  invalid={Boolean(formErrors.reorder_point)}
                />
                {formErrors.reorder_point ? <p className="text-xs text-destructive">{formErrors.reorder_point}</p> : null}
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
                          transaction.quantity > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'
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
              <Callout tone={readinessTone(identityReadiness)} title="Identity">
                {identityReadiness === 'ready'
                  ? 'Name, material, and price are present.'
                  : identityReadiness === 'warning'
                    ? 'The product has partial setup but still needs key sellable fields.'
                    : 'Start with the basic product identity and pricing fields.'}
              </Callout>

              <Callout tone={readinessTone(barcodeReadiness)} title="POS readiness">
                {barcodeReadiness === 'ready'
                  ? 'UPC present. This product can participate in barcode-driven POS flow.'
                  : 'No UPC yet. Product is still sellable, but manual lookup will be required at the register.'}
              </Callout>

              <Callout tone={readinessTone(stockReadiness)} title="Stock policy">
                {isCreate
                  ? 'Stock starts after creation. Reorder policy will apply once transactions begin.'
                  : stockReadiness === 'ready'
                    ? 'Current stock is above the reorder threshold.'
                    : stockReadiness === 'warning'
                      ? 'Current stock is near the reorder point.'
                      : 'Current stock is at or below zero and needs attention.'}
              </Callout>
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
                <span className={cn(marginDollars >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive')}>
                  {formatCurrency(marginDollars)}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Margin percent</span>
                <span className={cn(marginPct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive')}>
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
                  <p className="text-xs text-muted-foreground">Material</p>
                  <p className="mt-2 font-semibold">{selectedMaterial.name}</p>
                  <p className="mt-1 text-muted-foreground">{selectedMaterial.brand}</p>
                </div>
                <div className="rounded-md bg-background px-4 py-3">
                  <p className="text-xs text-muted-foreground">Cost per gram</p>
                  <p className="mt-2 font-semibold">${Number(selectedMaterial.cost_per_g).toFixed(4)}</p>
                </div>
                <div className="rounded-md bg-background px-4 py-3">
                  <p className="text-xs text-muted-foreground">Material stock</p>
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
