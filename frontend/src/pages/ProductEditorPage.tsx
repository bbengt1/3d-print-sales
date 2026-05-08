import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BadgeDollarSign,
  Boxes,
  Plus,
  ReceiptText,
  Save,
  ScanBarcode,
  Trash2,
  WandSparkles,
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/Tooltip';
import PageHeader from '@/components/layout/PageHeader';
import { cn, formatCurrency } from '@/lib/utils';
import { getApiErrorMessage } from '@/lib/apiError';
import type {
  InventoryTransaction,
  Material,
  PaginatedProducts,
  PaginatedTransactions,
  Product,
  ProductBarcodeGenerateResponse,
  ProductBOMComponentType,
  ProductBOMItemRequest,
  ProductBOMSummary,
} from '@/types';

const emptyForm = {
  name: '',
  description: '',
  material_id: '',
  upc: '',
  unit_price: 0,
  reorder_point: 5,
};

type BomDraftRow = ProductBOMItemRequest & { key: string };

const newBomRow = (): BomDraftRow => ({
  key: crypto.randomUUID(),
  component_type: 'material',
  material_id: '',
  component_product_id: '',
  quantity: 1,
  unit: 'g',
  waste_factor_pct: 0,
  notes: '',
});

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
  const [generatingBarcode, setGeneratingBarcode] = useState(false);
  const [barcodeGenerateError, setBarcodeGenerateError] = useState<string | null>(null);
  const [bomRows, setBomRows] = useState<BomDraftRow[]>([]);
  const [bomInitializedFor, setBomInitializedFor] = useState<string | null>(null);
  const [savingBom, setSavingBom] = useState(false);

  const { data: materials = [], isLoading: materialsLoading } = useQuery<Material[]>({
    queryKey: ['materials', 'active'],
    queryFn: () => api.get('/materials?active=true').then((r) => r.data),
  });

  const { data: product, isLoading: productLoading } = useQuery<Product>({
    queryKey: ['product', id],
    enabled: Boolean(id),
    queryFn: () => api.get(`/products/${id}`).then((r) => r.data),
  });

  const { data: productOptionsData } = useQuery<PaginatedProducts>({
    queryKey: ['products', 'active-options'],
    enabled: Boolean(id),
    queryFn: () => api.get('/products', { params: { is_active: true, limit: 100 } }).then((r) => r.data),
  });

  const { data: bomSummary, isLoading: bomLoading } = useQuery<ProductBOMSummary>({
    queryKey: ['product-bom', id],
    enabled: Boolean(id),
    queryFn: () => api.get(`/products/${id}/bom`).then((r) => r.data),
  });

  const { data: transactionsData, isLoading: transactionsLoading } = useQuery<PaginatedTransactions>({
    queryKey: ['transactions', id, 'editor'],
    enabled: Boolean(id),
    queryFn: () =>
      api.get('/inventory/transactions', { params: { product_id: id, limit: 6 } }).then((r) => r.data),
  });

  useEffect(() => {
    if (!product || initialized) return;
    setForm({
      name: product.name,
      description: product.description || '',
      material_id: product.material_id,
      upc: product.upc || '',
      unit_price: Number(product.unit_price),
      reorder_point: product.reorder_point,
    });
    setInitialized(true);
  }, [initialized, product]);

  useEffect(() => {
    if (!id || !bomSummary || bomInitializedFor === id) return;
    setBomRows(
      bomSummary.items.map((item) => ({
        key: item.id,
        component_type: item.component_type,
        material_id: item.material_id || '',
        component_product_id: item.component_product_id || '',
        quantity: Number(item.quantity),
        unit: item.unit,
        waste_factor_pct: Number(item.waste_factor_pct || 0),
        notes: item.notes || '',
      })),
    );
    setBomInitializedFor(id);
  }, [bomInitializedFor, bomSummary, id]);

  const selectedMaterial = materials.find((material) => material.id === form.material_id) || null;
  const unitCost = product?.unit_cost ?? 0;
  const stockQty = product?.stock_qty ?? 0;
  const marginDollars = Number(form.unit_price || 0) - Number(unitCost || 0);
  const marginPct = Number(form.unit_price || 0) > 0 ? (marginDollars / Number(form.unit_price || 1)) * 100 : 0;
  const inventoryValue = stockQty * Number(unitCost || 0);
  const recentTransactions = transactionsData?.items || [];
  const productOptions = (productOptionsData?.items || []).filter((candidate) => candidate.id !== id);

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
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to save product'));
    } finally {
      setSaving(false);
    }
  };

  const generateBarcode = async () => {
    setBarcodeGenerateError(null);

    if (form.upc.trim()) {
      const shouldReplace = window.confirm(
        'Replace the current UPC / barcode with a newly generated internal UPC-A code?',
      );
      if (!shouldReplace) return;
    }

    setGeneratingBarcode(true);
    try {
      const response = await api.post<ProductBarcodeGenerateResponse>('/products/barcode/generate');
      setForm((current) => ({ ...current, upc: response.data.upc }));
      toast.success('Generated internal UPC-A barcode');
    } catch (err) {
      const message = getApiErrorMessage(err, 'Failed to generate barcode');
      setBarcodeGenerateError(message);
      toast.error(message);
    } finally {
      setGeneratingBarcode(false);
    }
  };

  const saveBom = async () => {
    if (!id) return;
    const invalidRow = bomRows.find((row) => {
      if (Number(row.quantity) <= 0 || Number(row.waste_factor_pct) < 0 || !row.unit.trim()) return true;
      if (row.component_type === 'material') return !row.material_id;
      return !row.component_product_id;
    });

    if (invalidRow) {
      toast.error('Complete each BOM row before saving');
      return;
    }

    setSavingBom(true);
    try {
      const items = bomRows.map((row) => ({
        component_type: row.component_type,
        material_id: row.component_type === 'material' ? row.material_id : null,
        component_product_id: row.component_type === 'product' ? row.component_product_id : null,
        quantity: Number(row.quantity),
        unit: row.unit.trim(),
        waste_factor_pct: Number(row.waste_factor_pct || 0),
        notes: row.notes?.trim() || null,
      }));
      await api.put(`/products/${id}/bom`, { items });
      toast.success('Bill of materials saved');
      queryClient.invalidateQueries({ queryKey: ['product-bom', id] });
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to save bill of materials'));
    } finally {
      setSavingBom(false);
    }
  };

  const updateBomRow = (key: string, updates: Partial<BomDraftRow>) => {
    setBomRows((current) =>
      current.map((row) => {
        if (row.key !== key) return row;
        const next = { ...row, ...updates };
        if (updates.component_type === 'material') {
          next.component_product_id = '';
          if (!updates.unit) next.unit = 'g';
        }
        if (updates.component_type === 'product') {
          next.material_id = '';
          if (!updates.unit) next.unit = 'each';
        }
        return next;
      }),
    );
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
            <Button asChild variant="outline">
              <Link to="/product-studio">
                <ArrowLeft className="h-4 w-4" />
                Back to catalog
              </Link>
            </Button>
            {!isCreate ? (
              <Button asChild variant="outline">
                <Link to={`/product-studio/products/${id}`}>
                  View record
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            ) : null}
          </>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
        <section className="space-y-6">
          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <ReceiptText className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-base font-semibold">Identity and sellable details</h2>
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <div className="lg:col-span-2 space-y-1.5">
                <Label htmlFor="product-name" required>Product name</Label>
                <Input
                  id="product-name"
                  value={form.name}
                  onChange={(event) => {
                    setForm((current) => ({ ...current, name: event.target.value }));
                    setFormErrors((current) => ({ ...current, name: '' }));
                  }}
                  error={formErrors.name}
                  placeholder="Desk Dragon, Tool Holder, Display Plaque..."
                />
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
                <TooltipProvider>
                  <div className="relative">
                    <ScanBarcode className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      id="product-upc"
                      value={form.upc}
                      onChange={(event) => {
                        setForm((current) => ({ ...current, upc: event.target.value }));
                        setBarcodeGenerateError(null);
                      }}
                      className="pl-9 pr-11"
                      placeholder="012345678901"
                      aria-describedby={barcodeGenerateError ? 'product-upc-generate-error' : undefined}
                    />
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2"
                          onClick={generateBarcode}
                          disabled={generatingBarcode || saving}
                          aria-label={form.upc.trim() ? 'Replace UPC barcode' : 'Generate UPC barcode'}
                        >
                          <WandSparkles className={cn('h-4 w-4', generatingBarcode && 'animate-pulse')} />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {form.upc.trim() ? 'Replace with generated internal UPC-A' : 'Generate internal UPC-A'}
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </TooltipProvider>
                {barcodeGenerateError ? (
                  <p id="product-upc-generate-error" className="text-xs text-destructive">
                    {barcodeGenerateError}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Generated codes use the internal UPC-A 04 namespace and are reserved when saved.
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="product-material" required>Material</Label>
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
                  error={formErrors.unit_price}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="product-reorder">Reorder point</Label>
                <Input
                  id="product-reorder"
                  type="number"
                  min="0"
                  value={form.reorder_point}
                  onChange={(event) => setForm((current) => ({ ...current, reorder_point: Number(event.target.value) }))}
                  error={formErrors.reorder_point}
                />
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
                <Button asChild variant="outline" size="lg" className="min-h-12 px-5 font-semibold">
                  <Link to={`/product-studio/products/${id}`}>
                    Open detail record
                  </Link>
                </Button>
              ) : null}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Boxes className="h-5 w-5 text-muted-foreground" />
                <h2 className="text-base font-semibold">Bill of materials</h2>
              </div>
              {!isCreate ? (
                <Button type="button" variant="outline" size="sm" onClick={() => setBomRows((current) => [...current, newBomRow()])}>
                  <Plus className="h-4 w-4" />
                  Add part
                </Button>
              ) : null}
            </div>

            {isCreate ? (
              <EmptyState
                icon="products"
                title="Parts can be added after creation"
                description="Save the product first, then attach raw materials or stocked component products."
                className="py-10"
              />
            ) : bomLoading ? (
              <SkeletonTable rows={3} cols={5} />
            ) : !bomRows.length ? (
              <EmptyState
                compact
                icon="products"
                title="No parts tracked yet."
                description="Add material or product components to estimate cost and buildable quantity."
                className="mt-4"
              />
            ) : (
              <div className="mt-5 space-y-4">
                {bomRows.map((row, index) => (
                  <div key={row.key} className="rounded-md border border-border bg-background p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <p className="text-sm font-medium">Part {index + 1}</p>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => setBomRows((current) => current.filter((item) => item.key !== row.key))}
                        aria-label={`Remove part ${index + 1}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="grid gap-3 lg:grid-cols-[0.8fr_1.4fr_0.6fr_0.6fr_0.7fr]">
                      <div className="space-y-1.5">
                        <Label htmlFor={`bom-type-${row.key}`}>Type</Label>
                        <select
                          id={`bom-type-${row.key}`}
                          value={row.component_type}
                          onChange={(event) =>
                            updateBomRow(row.key, { component_type: event.target.value as ProductBOMComponentType })
                          }
                          className={selectClass('bom')}
                        >
                          <option value="material">Material</option>
                          <option value="product">Product</option>
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`bom-component-${row.key}`}>Component</Label>
                        {row.component_type === 'material' ? (
                          <select
                            id={`bom-component-${row.key}`}
                            value={row.material_id || ''}
                            onChange={(event) => updateBomRow(row.key, { material_id: event.target.value })}
                            className={selectClass('bom')}
                          >
                            <option value="">Select material...</option>
                            {materials.map((material) => (
                              <option key={material.id} value={material.id}>
                                {material.name} ({material.brand})
                              </option>
                            ))}
                          </select>
                        ) : (
                          <select
                            id={`bom-component-${row.key}`}
                            value={row.component_product_id || ''}
                            onChange={(event) => updateBomRow(row.key, { component_product_id: event.target.value })}
                            className={selectClass('bom')}
                          >
                            <option value="">Select product...</option>
                            {productOptions.map((candidate) => (
                              <option key={candidate.id} value={candidate.id}>
                                {candidate.sku} - {candidate.name}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`bom-qty-${row.key}`}>Qty</Label>
                        <Input
                          id={`bom-qty-${row.key}`}
                          type="number"
                          min="0.0001"
                          step="0.0001"
                          value={row.quantity}
                          onChange={(event) => updateBomRow(row.key, { quantity: Number(event.target.value) })}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`bom-unit-${row.key}`}>Unit</Label>
                        <Input
                          id={`bom-unit-${row.key}`}
                          value={row.unit}
                          onChange={(event) => updateBomRow(row.key, { unit: event.target.value })}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`bom-waste-${row.key}`}>Waste %</Label>
                        <Input
                          id={`bom-waste-${row.key}`}
                          type="number"
                          min="0"
                          step="0.1"
                          value={row.waste_factor_pct}
                          onChange={(event) => updateBomRow(row.key, { waste_factor_pct: Number(event.target.value) })}
                        />
                      </div>
                    </div>
                    <div className="mt-3 space-y-1.5">
                      <Label htmlFor={`bom-notes-${row.key}`}>Notes</Label>
                      <Input
                        id={`bom-notes-${row.key}`}
                        value={row.notes || ''}
                        onChange={(event) => updateBomRow(row.key, { notes: event.target.value })}
                        placeholder="Optional production note"
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {!isCreate ? (
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                <div className="text-sm">
                  <span className="text-muted-foreground">Estimated BOM cost </span>
                  <span className="font-semibold">{formatCurrency(Number(bomSummary?.estimated_unit_cost || 0))}</span>
                  <span className="mx-2 text-muted-foreground">|</span>
                  <span className="text-muted-foreground">Buildable </span>
                  <span className="font-semibold">{bomSummary?.buildable_quantity ?? '-'}</span>
                </div>
                <Button type="button" onClick={saveBom} disabled={savingBom}>
                  <Save className="h-4 w-4" />
                  {savingBom ? 'Saving...' : 'Save BOM'}
                </Button>
              </div>
            ) : null}

            {bomSummary?.blockers.length ? (
              <div className="mt-4 rounded-md border border-warning/35 bg-warning/10 px-4 py-3 text-sm text-warning">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <p>{bomSummary.blockers[0]}</p>
                </div>
              </div>
            ) : null}
          </div>

          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <Boxes className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-base font-semibold">Stock and activity context</h2>
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
              <EmptyState
                compact
                icon="reports"
                title="No stock activity recorded yet."
                description="Adjustments and production entries will appear here."
                className="mt-4"
              />
            ) : (
              <div className="mt-4 space-y-3">
                {recentTransactions.map((transaction: InventoryTransaction) => (
                  <div key={transaction.id} className="rounded-md border border-border bg-background px-4 py-3">
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
                          transaction.quantity > 0 ? 'text-success' : 'text-destructive'
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
              <h2 className="text-base font-semibold">Readiness and margin</h2>
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
                <span className={cn(marginDollars >= 0 ? 'text-success' : 'text-destructive')}>
                  {formatCurrency(marginDollars)}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Margin percent</span>
                <span className={cn(marginPct >= 0 ? 'text-success' : 'text-destructive')}>
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
            <h2 className="text-base font-semibold">Material context</h2>
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
