import { useDeferredValue, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Minus, Plus, Receipt, Search, ShoppingBasket, Trash2, UserRound, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import EmptyState from '@/components/ui/EmptyState';
import { cn, formatCurrency } from '@/lib/utils';
import {
  addProductToCart,
  buildPOSCheckoutPayload,
  getCartSubtotal,
  getCartTotal,
  getProductCartQuantity,
  POS_PAYMENT_METHODS,
  removeProductFromCart,
  updateCartLineQuantity,
  type POSCartLine,
} from '@/pages/posCart';
import type { Customer, PaginatedProducts, Product, Sale } from '@/types';

const today = new Date().toISOString().split('T')[0];
const POS_PRODUCT_PAGE_SIZE = 100;

function getErrorDetail(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof error.response === 'object' &&
    error.response !== null &&
    'data' in error.response &&
    typeof error.response.data === 'object' &&
    error.response.data !== null &&
    'detail' in error.response &&
    typeof error.response.detail === 'string'
  ) {
    return error.response.detail;
  }

  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof error.response === 'object' &&
    error.response !== null &&
    'data' in error.response &&
    typeof error.response.data === 'object' &&
    error.response.data !== null &&
    'detail' in error.response.data &&
    typeof error.response.data.detail === 'string'
  ) {
    return error.response.data.detail;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return 'Failed to complete POS checkout';
}

export default function POSPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [cart, setCart] = useState<POSCartLine[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [taxCollected, setTaxCollected] = useState(0);
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const deferredSearch = useDeferredValue(search);

  const { data: productsData, isLoading: productsLoading, isError: productsError } = useQuery<PaginatedProducts>({
    queryKey: ['products', 'pos'],
    queryFn: async () => {
      const items: Product[] = [];
      let skip = 0;
      let total = 0;

      do {
        const response = await api.get<PaginatedProducts>('/products', {
          params: {
            limit: POS_PRODUCT_PAGE_SIZE,
            skip,
            is_active: true,
          },
        });
        const page = response.data;
        items.push(...page.items);
        total = page.total;
        skip += page.items.length;
      } while (skip < total);

      return {
        items,
        total,
        skip: 0,
        limit: items.length || POS_PRODUCT_PAGE_SIZE,
      };
    },
  });

  const { data: customers = [] } = useQuery<Customer[]>({
    queryKey: ['customers', 'pos'],
    queryFn: () => api.get('/customers').then((r) => r.data),
  });

  const products = (productsData?.items || []).filter((product) => product.is_active);
  const normalizedSearch = deferredSearch.trim().toLowerCase();
  const filteredProducts = products.filter((product) => {
    if (!normalizedSearch) return true;
    return [product.name, product.sku, product.upc || ''].some((value) =>
      value.toLowerCase().includes(normalizedSearch)
    );
  });

  const subtotal = getCartSubtotal(cart);
  const total = getCartTotal(cart, taxCollected);

  const resetCheckoutFields = () => {
    setCart([]);
    setSelectedCustomerId('');
    setCustomerName('');
    setPaymentMethod('cash');
    setTaxCollected(0);
    setNotes('');
    setCheckoutError(null);
  };

  const handleAddProduct = (product: Product) => {
    setSuccessMessage(null);
    setCheckoutError(null);
    setCart((prev) => addProductToCart(prev, product));
  };

  const handleCheckout = async () => {
    if (!cart.length) {
      toast.error('Add at least one product to the cart');
      return;
    }

    setSaving(true);
    setCheckoutError(null);
    setSuccessMessage(null);
    try {
      const payload = buildPOSCheckoutPayload({
        cart,
        date: today,
        customerId: selectedCustomerId,
        customerName,
        taxCollected,
        paymentMethod,
        notes,
      });
      const response = await api.post<Sale>('/pos/checkout', payload);
      const sale = response.data;

      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['sales'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-alerts'] });
      queryClient.invalidateQueries({ queryKey: ['sales-metrics'] });

      setSuccessMessage(`Sale ${sale.sale_number} completed for ${formatCurrency(sale.total)}.`);
      resetCheckoutFields();
      toast.success(`POS checkout complete: ${sale.sale_number}`);
    } catch (error: unknown) {
      const detail = getErrorDetail(error);
      setCheckoutError(detail);
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-3xl border border-border bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.16),_transparent_28%),linear-gradient(135deg,_rgba(26,32,44,1),_rgba(60,72,88,0.98))] p-6 text-white shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-white/70">Cashier</p>
            <h1 className="mt-2 flex items-center gap-3 text-3xl font-bold">
              <Receipt className="h-8 w-8" />
              POS Checkout
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-white/80">
              Product-first checkout for quick counter sales. Because making staff click through the general sales form for every walk-up sale would be a weird hobby.
            </p>
          </div>
          <div className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm">
            <p className="text-white/65">Checkout date</p>
            <p className="mt-1 text-lg font-semibold">{today}</p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-3">
            <p className="text-xs uppercase tracking-[0.25em] text-white/60">Cart Subtotal</p>
            <p className="mt-2 text-2xl font-semibold">{formatCurrency(subtotal)}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-3">
            <p className="text-xs uppercase tracking-[0.25em] text-white/60">Tax Collected</p>
            <p className="mt-2 text-2xl font-semibold">{formatCurrency(taxCollected)}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-3">
            <p className="text-xs uppercase tracking-[0.25em] text-white/60">Total</p>
            <p className="mt-2 text-2xl font-semibold">{formatCurrency(total)}</p>
          </div>
        </div>
      </div>

      {successMessage && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-emerald-900" role="status">
          {successMessage}
        </div>
      )}

      {checkoutError && (
        <div className="rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-destructive" role="alert">
          {checkoutError}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(360px,0.9fr)]">
        <section className="space-y-4">
          <div className="rounded-3xl border border-border bg-card p-5 shadow-sm">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-xl font-semibold">Product Catalog</h2>
                <p className="text-sm text-muted-foreground">Search by name, SKU, or UPC and tap products into the cart.</p>
              </div>
              <div className="relative w-full md:max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search products..."
                  aria-label="Search products"
                  className="w-full rounded-xl border border-input bg-background py-2.5 pl-10 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
          </div>

          {productsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-28 animate-pulse rounded-3xl border border-border bg-card" />
              ))}
            </div>
          ) : productsError ? (
            <div className="rounded-3xl border border-destructive/40 bg-destructive/10 p-6 text-destructive">
              Unable to load products for POS checkout.
            </div>
          ) : !filteredProducts.length ? (
            <EmptyState
              icon="search"
              title={products.length ? 'No products match that search' : 'No active products available'}
              description={
                products.length
                  ? 'Try a different name or SKU.'
                  : 'Add active products with stock before using the POS screen.'
              }
            />
          ) : (
            <div className="space-y-3">
              {filteredProducts.map((product) => {
                const cartQty = getProductCartQuantity(cart, product.id);
                const remainingStock = product.stock_qty - cartQty;
                const outOfStock = remainingStock <= 0;

                return (
                  <article
                    key={product.id}
                    className={cn(
                      'rounded-3xl border border-border bg-card p-4 shadow-sm transition-colors',
                      outOfStock ? 'opacity-70' : 'hover:border-primary/40'
                    )}
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">{product.sku}</p>
                        <h3 className="mt-2 break-words text-lg font-semibold leading-tight">{product.name}</h3>
                        {product.description && (
                          <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{product.description}</p>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-3 lg:min-w-56 lg:grid-cols-2">
                        <div className="rounded-2xl bg-background px-3 py-2 text-sm">
                          <p className="text-xs uppercase tracking-[0.15em] text-muted-foreground">Stock</p>
                          <p className={cn('mt-1 font-semibold', product.stock_qty <= product.reorder_point && 'text-amber-600')}>
                            {product.stock_qty}
                          </p>
                        </div>
                        <div className="rounded-2xl bg-background px-3 py-2 text-sm">
                          <p className="text-xs uppercase tracking-[0.15em] text-muted-foreground">In cart</p>
                          <p className="mt-1 font-semibold">{cartQty}</p>
                        </div>
                      </div>

                      <div className="flex flex-col gap-3 lg:min-w-52 lg:items-end">
                        <div className="inline-flex w-fit max-w-full self-start rounded-full bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground lg:self-end">
                          {formatCurrency(product.unit_price)}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleAddProduct(product)}
                          disabled={outOfStock}
                          aria-label={`Add ${product.name} to cart`}
                          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground lg:w-52"
                        >
                          <Plus className="h-4 w-4" />
                          {outOfStock ? 'Stock maxed in cart' : 'Add to cart'}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
          <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold">Cart</h2>
                <p className="text-sm text-muted-foreground">Keep it moving. This is the fast lane.</p>
              </div>
              <div className="rounded-full bg-accent px-3 py-1 text-sm font-medium text-accent-foreground">
                {cart.reduce((sum, line) => sum + line.quantity, 0)} items
              </div>
            </div>

            {!cart.length ? (
              <div className="mt-6 rounded-3xl border border-dashed border-border bg-background/70 p-8 text-center">
                <ShoppingBasket className="mx-auto h-10 w-10 text-muted-foreground" />
                <p className="mt-4 text-lg font-medium">Cart is empty</p>
                <p className="mt-2 text-sm text-muted-foreground">Add products from the catalog to start a sale.</p>
              </div>
            ) : (
              <div className="mt-5 space-y-3">
                {cart.map((line) => (
                  <div key={line.product_id} className="rounded-2xl border border-border bg-background/80 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{line.name}</p>
                        <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">{line.sku}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setCart((prev) => removeProductFromCart(prev, line.product_id))}
                        aria-label={`Remove ${line.name} from cart`}
                        className="rounded-full p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>

                    <div className="mt-4 flex items-center justify-between gap-3">
                      <div className="inline-flex items-center rounded-full border border-border bg-card">
                        <button
                          type="button"
                          onClick={() => setCart((prev) => updateCartLineQuantity(prev, line.product_id, line.quantity - 1))}
                          aria-label={`Decrease quantity for ${line.name}`}
                          className="rounded-l-full px-3 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                        >
                          <Minus className="h-4 w-4" />
                        </button>
                        <span aria-label={`${line.name} quantity`} className="min-w-12 px-3 text-center font-semibold">
                          {line.quantity}
                        </span>
                        <button
                          type="button"
                          onClick={() => setCart((prev) => updateCartLineQuantity(prev, line.product_id, line.quantity + 1))}
                          disabled={line.quantity >= line.stock_qty}
                          aria-label={`Increase quantity for ${line.name}`}
                          className="rounded-r-full px-3 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:text-muted-foreground/40"
                        >
                          <Plus className="h-4 w-4" />
                        </button>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-muted-foreground">{formatCurrency(line.unit_price)} each</p>
                        <p className="font-semibold">{formatCurrency(line.unit_price * line.quantity)}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <UserRound className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-xl font-semibold">Checkout</h2>
            </div>

            <div className="mt-5 space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Customer</label>
                <select
                  value={selectedCustomerId}
                  onChange={(e) => {
                    setSelectedCustomerId(e.target.value);
                    setCheckoutError(null);
                    if (e.target.value) {
                      setCustomerName('');
                    }
                  }}
                  aria-label="Customer"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Guest checkout</option>
                  {customers.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      {customer.name}
                    </option>
                  ))}
                </select>
              </div>

              {!selectedCustomerId && (
                <div>
                  <label className="mb-1 block text-sm font-medium">Guest name</label>
                  <input
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="Optional walk-up customer name"
                    aria-label="Guest name"
                    className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              )}

              <div>
                <label className="mb-1 block text-sm font-medium">Payment method</label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  aria-label="Payment method"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {POS_PAYMENT_METHODS.map((method) => (
                    <option key={method.value} value={method.value}>
                      {method.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Tax collected</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={taxCollected}
                  onChange={(e) => setTaxCollected(Math.max(0, Number(e.target.value) || 0))}
                  aria-label="Tax collected"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Notes</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  placeholder="Optional booth or counter notes"
                  aria-label="Notes"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>

            <div className="mt-6 rounded-3xl bg-background p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Subtotal</span>
                <span>{formatCurrency(subtotal)}</span>
              </div>
              <div className="mt-2 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Tax</span>
                <span>{formatCurrency(taxCollected)}</span>
              </div>
              <div className="mt-4 flex items-center justify-between border-t border-border pt-4 text-lg font-semibold">
                <span>Total</span>
                <span>{formatCurrency(total)}</span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleCheckout}
              disabled={saving || !cart.length}
              className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
            >
              {saving ? 'Processing checkout...' : 'Complete checkout'}
            </button>

            {!!cart.length && (
              <button
                type="button"
                onClick={resetCheckoutFields}
                className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-border px-4 py-3 font-medium transition-colors hover:bg-accent"
              >
                <XCircle className="h-4 w-4" />
                Clear cart
              </button>
            )}

            <div className="mt-4 rounded-2xl border border-amber-300/60 bg-amber-50 p-3 text-sm text-amber-900">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <p>POS checkout will block oversell when cart quantity exceeds available stock. Fancy concept, I know.</p>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
