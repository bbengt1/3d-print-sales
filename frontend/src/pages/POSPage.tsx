import { useDeferredValue, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowRight,
  Barcode,
  CheckCircle2,
  Clock3,
  Minus,
  Plus,
  Receipt,
  Search,
  ShoppingBasket,
  Trash2,
  UserRound,
  Users,
  WalletCards,
  XCircle,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import api from '@/api/client';
import EmptyState from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';
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
import PageHeader from '@/components/layout/PageHeader';
import { KPI, KPIStrip } from '@/components/layout/KPIStrip';
import type { Customer, PaginatedProducts, PaginatedSales, Product, Sale, SaleListItem } from '@/types';

const today = new Date().toISOString().split('T')[0];
const POS_PRODUCT_PAGE_SIZE = 100;
const SALES_INBOX_PAGE_SIZE = 6;

type CustomerMode = 'guest' | 'existing' | 'new';
type ProductFilter = 'all' | 'scannable' | 'low-stock' | 'in-cart';

interface QuickFilterButtonProps {
  active: boolean;
  label: string;
  detail: string;
  onClick: () => void;
}

function QuickFilterButton({ active, label, detail, onClick }: QuickFilterButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-md border px-4 py-3 text-left transition-colors',
        active
          ? 'border-primary bg-primary/10 text-foreground shadow-sm'
          : 'border-border bg-background/80 text-muted-foreground hover:border-primary/40 hover:text-foreground'
      )}
    >
      <p className="text-sm font-semibold">{label}</p>
      <p className="mt-1 text-xs">{detail}</p>
    </button>
  );
}

interface CustomerModeButtonProps {
  active: boolean;
  icon: typeof UserRound;
  label: string;
  detail: string;
  onClick: () => void;
}

function CustomerModeButton({ active, icon: Icon, label, detail, onClick }: CustomerModeButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-md border px-4 py-4 text-left transition-colors',
        active
          ? 'border-primary bg-primary/10 text-foreground shadow-sm'
          : 'border-border bg-background/85 text-muted-foreground hover:border-primary/40 hover:text-foreground'
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            'rounded-md p-2',
            active ? 'bg-primary text-primary-foreground' : 'bg-accent text-accent-foreground'
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <p className="font-semibold">{label}</p>
          <p className="mt-1 text-xs">{detail}</p>
        </div>
      </div>
    </button>
  );
}

interface PaymentButtonProps {
  active: boolean;
  label: string;
  onClick: () => void;
}

function PaymentButton({ active, label, onClick }: PaymentButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-md border px-4 py-3 text-sm font-semibold transition-colors',
        active
          ? 'border-primary bg-primary text-primary-foreground shadow-sm'
          : 'border-border bg-background hover:border-primary/40 hover:text-foreground'
      )}
    >
      {label}
    </button>
  );
}

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

function SalesInboxCard({ sale }: { sale: SaleListItem }) {
  const statusTone =
    sale.status === 'refunded'
      ? 'border-destructive/20 bg-destructive/5 text-destructive'
      : sale.status === 'pending'
        ? 'border-amber-300/50 bg-amber-50 text-amber-900'
        : 'border-emerald-300/40 bg-emerald-50 text-emerald-900';

  return (
    <Link
      to={`/sell/sales/${sale.id}`}
      className="block rounded-md border border-border bg-background/85 p-4 no-underline transition-colors hover:border-primary/35"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">{sale.sale_number}</p>
          <p className="mt-2 truncate text-base font-semibold text-foreground">{sale.customer_name || 'Guest checkout'}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {sale.date} • {sale.channel_name || 'Direct'} • {sale.item_count} items
          </p>
        </div>
        <div className={cn('rounded-full border px-3 py-1 text-xs font-semibold capitalize', statusTone)}>
          {sale.status}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 text-sm">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Payment</p>
          <p className="mt-1 capitalize text-foreground">{sale.payment_method || 'Unknown'}</p>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Total</p>
          <p className="mt-1 font-semibold text-foreground">{formatCurrency(sale.total)}</p>
        </div>
      </div>
    </Link>
  );
}

export default function POSPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [productFilter, setProductFilter] = useState<ProductFilter>('all');
  const [cart, setCart] = useState<POSCartLine[]>([]);
  const [customerMode, setCustomerMode] = useState<CustomerMode>('guest');
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [taxCollected, setTaxCollected] = useState(0);
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [scanCode, setScanCode] = useState('');
  const [scanStatus, setScanStatus] = useState<string | null>(null);
  const deferredSearch = useDeferredValue(search);
  const scanBufferRef = useRef('');
  const scanTimeoutRef = useRef<number | null>(null);

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

  const { data: salesInboxData, isLoading: salesInboxLoading } = useQuery<PaginatedSales>({
    queryKey: ['sales', 'sell-inbox'],
    queryFn: () =>
      api
        .get('/sales', {
          params: {
            skip: 0,
            limit: SALES_INBOX_PAGE_SIZE,
          },
        })
        .then((r) => r.data),
  });

  const salesInbox = salesInboxData?.items || [];
  const products = (productsData?.items || []).filter((product) => product.is_active);
  const normalizedSearch = deferredSearch.trim().toLowerCase();
  const filteredProducts = products.filter((product) => {
    const searchMatch =
      !normalizedSearch ||
      [product.name, product.sku, product.upc || ''].some((value) => value.toLowerCase().includes(normalizedSearch));

    if (!searchMatch) return false;

    const cartQty = getProductCartQuantity(cart, product.id);
    switch (productFilter) {
      case 'scannable':
        return Boolean(product.upc);
      case 'low-stock':
        return product.stock_qty <= product.reorder_point;
      case 'in-cart':
        return cartQty > 0;
      default:
        return true;
    }
  });

  const subtotal = getCartSubtotal(cart);
  const total = getCartTotal(cart, taxCollected);
  const cartUnits = cart.reduce((sum, line) => sum + line.quantity, 0);
  const scannableCount = products.filter((product) => Boolean(product.upc)).length;
  const lowStockCount = products.filter((product) => product.stock_qty <= product.reorder_point).length;
  const salesNeedingAttention = salesInbox.filter((sale) => ['pending', 'refunded'].includes(sale.status)).length;

  const resetCheckoutFields = () => {
    setCart([]);
    setCustomerMode('guest');
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
    setScanStatus(null);
    setCart((prev) => addProductToCart(prev, product));
  };

  const handleResolveScan = async (code: string) => {
    const normalizedCode = code.trim();
    if (!normalizedCode) return;

    setCheckoutError(null);
    setSuccessMessage(null);
    setScanStatus(null);

    try {
      const response = await api.post<Product>('/pos/scan/resolve', { code: normalizedCode });
      const product = response.data;
      setCart((prev) => addProductToCart(prev, product));
      setScanStatus(`Scanned ${product.name} (${product.sku})`);
      toast.success(`Scanned ${product.name}`);
      setScanCode('');
    } catch (error: unknown) {
      const detail = getErrorDetail(error);
      setScanStatus(detail);
      toast.error(detail);
    }
  };

  useEffect(() => {
    const clearBuffer = () => {
      scanBufferRef.current = '';
      if (scanTimeoutRef.current) {
        window.clearTimeout(scanTimeoutRef.current);
        scanTimeoutRef.current = null;
      }
    };

    const isEditableTarget = (target: EventTarget | null) =>
      target instanceof HTMLElement &&
      (target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) return;

      if (event.key === 'Enter') {
        if (scanBufferRef.current.length >= 8) {
          event.preventDefault();
          void handleResolveScan(scanBufferRef.current);
        }
        clearBuffer();
        return;
      }

      if (event.key.length !== 1 || event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }

      scanBufferRef.current += event.key;
      if (scanTimeoutRef.current) {
        window.clearTimeout(scanTimeoutRef.current);
      }
      scanTimeoutRef.current = window.setTimeout(() => {
        clearBuffer();
      }, 150);
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      clearBuffer();
    };
  }, []);

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
        customerId: customerMode === 'existing' ? selectedCustomerId : '',
        customerName: customerMode === 'new' ? customerName : null,
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
      <PageHeader
        title="Register"
        description={`Cart: ${cartUnits} ${cartUnits === 1 ? 'unit' : 'units'} · ${formatCurrency(total)}`}
      >
        <KPIStrip columns={4}>
          <KPI label="Cart total" value={formatCurrency(total)} sub={`${cartUnits} units`} />
          <KPI label="Barcode ready" value={scannableCount} sub="Active UPC products" />
          <KPI
            label="Low stock"
            value={lowStockCount}
            sub="At or below reorder point"
            tone={lowStockCount > 0 ? 'warning' : 'default'}
          />
          <KPI
            label="Sales inbox"
            value={salesNeedingAttention}
            sub="Pending or refunded sales"
            tone={salesNeedingAttention > 0 ? 'warning' : 'default'}
          />
        </KPIStrip>
      </PageHeader>

      {successMessage ? (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 px-5 py-4 text-emerald-900 shadow-sm" role="status">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Checkout complete</p>
              <p className="mt-1 text-sm">{successMessage}</p>
            </div>
          </div>
        </div>
      ) : null}

      {checkoutError ? (
        <div className="rounded-lg border border-destructive/35 bg-destructive/10 px-5 py-4 text-destructive shadow-sm" role="alert">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Checkout blocked</p>
              <p className="mt-1 text-sm">{checkoutError}</p>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(360px,0.95fr)]">
        <section className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
              <div>
                <div className="flex items-center gap-2">
                  <Barcode className="h-5 w-5 text-primary" />
                  <h2 className="text-xl font-semibold">Scanner lane</h2>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Keep wedge scanning obvious. Operators can scan into the field below or scan with focus outside other form controls.
                </p>
                <form
                  className="mt-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleResolveScan(scanCode);
                  }}
                >
                  <label className="mb-2 block text-sm font-medium" htmlFor="pos-scan-code">
                    Scan barcode
                  </label>
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <input
                      id="pos-scan-code"
                      value={scanCode}
                      onChange={(event) => setScanCode(event.target.value)}
                      placeholder="Scan UPC and press Enter"
                      aria-label="Scan barcode"
                      className="min-h-14 flex-1 rounded-md border border-input bg-background px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    <Button type="submit" size="lg" className="min-h-14 font-semibold">
                      Resolve scan
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </div>
                </form>
              </div>

              <div className="rounded-lg border border-border bg-background/80 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Lane rules</p>
                <div className="mt-3 space-y-3 text-sm text-muted-foreground">
                  <p>Exact UPC match only.</p>
                  <p>Only active, in-stock products resolve.</p>
                  <p>Failed scans leave the cart unchanged.</p>
                </div>
              </div>
            </div>

            {scanStatus ? (
              <div
                className={cn(
                  'mt-4 rounded-md border px-4 py-3 text-sm',
                  scanStatus.startsWith('Scanned ')
                    ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
                    : 'border-amber-300 bg-amber-50 text-amber-900'
                )}
              >
                {scanStatus}
              </div>
            ) : null}
          </div>

          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-xl font-semibold">Catalog lane</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Search by product name, SKU, or UPC. Quick filters reduce choice overload during busy counter traffic.
                </p>
              </div>
              <div className="relative w-full lg:max-w-sm">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search products..."
                  aria-label="Search products"
                  className="min-h-14 w-full rounded-md border border-input bg-background py-3 pl-11 pr-4 text-base focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <QuickFilterButton active={productFilter === 'all'} label="All products" detail={`${products.length} active items`} onClick={() => setProductFilter('all')} />
              <QuickFilterButton active={productFilter === 'scannable'} label="Scanner-ready" detail={`${scannableCount} products with UPC`} onClick={() => setProductFilter('scannable')} />
              <QuickFilterButton active={productFilter === 'low-stock'} label="Low stock" detail={`${lowStockCount} products need attention`} onClick={() => setProductFilter('low-stock')} />
              <QuickFilterButton active={productFilter === 'in-cart'} label="In cart" detail={`${cart.length} product lines selected`} onClick={() => setProductFilter('in-cart')} />
            </div>
          </div>

          {productsLoading ? (
            <div className="grid gap-3 md:grid-cols-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-48 animate-pulse rounded-lg border border-border bg-card" />
              ))}
            </div>
          ) : productsError ? (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-6 text-destructive">
              Unable to load products for POS checkout.
            </div>
          ) : !filteredProducts.length ? (
            <EmptyState
              icon="sales"
              title={products.length ? 'No products match the current lane filters' : 'No active products available'}
              description={
                products.length
                  ? 'Try a different search term or filter combination.'
                  : 'Add active products with stock before using the POS register.'
              }
              className="rounded-lg border border-border bg-card"
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {filteredProducts.map((product) => {
                const cartQty = getProductCartQuantity(cart, product.id);
                const remainingStock = product.stock_qty - cartQty;
                const outOfStock = remainingStock <= 0;
                const lowStock = product.stock_qty <= product.reorder_point;

                return (
                  <article
                    key={product.id}
                    className={cn(
                      'rounded-lg border border-border bg-card p-5 shadow-sm transition-colors',
                      outOfStock ? 'opacity-70' : 'hover:border-primary/35'
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">{product.sku}</p>
                        <h3 className="mt-2 text-lg font-semibold leading-tight">{product.name}</h3>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {product.upc ? `UPC ${product.upc}` : 'No UPC assigned yet'}
                        </p>
                      </div>
                      <div className="rounded-md bg-accent px-4 py-3 text-sm font-semibold text-accent-foreground">
                        {formatCurrency(product.unit_price)}
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-md bg-background px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Stock</p>
                        <p className={cn('mt-2 text-lg font-semibold', lowStock && 'text-amber-600')}>{product.stock_qty}</p>
                      </div>
                      <div className="rounded-md bg-background px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">In cart</p>
                        <p className="mt-2 text-lg font-semibold">{cartQty}</p>
                      </div>
                      <div className="rounded-md bg-background px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Scanner</p>
                        <p className="mt-2 text-sm font-semibold">{product.upc ? 'Ready' : 'Manual only'}</p>
                      </div>
                    </div>

                    <Button
                      type="button"
                      onClick={() => handleAddProduct(product)}
                      disabled={outOfStock}
                      aria-label={`Add ${product.name} to cart`}
                      size="lg"
                      className="mt-4 min-h-14 w-full font-semibold"
                    >
                      <Plus className="h-4 w-4" />
                      {outOfStock ? 'Stock maxed in cart' : 'Add to cart'}
                    </Button>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold">Cart and checkout</h2>
                <p className="mt-2 text-sm text-muted-foreground">Large controls, shorter decisions, faster recovery.</p>
              </div>
              <div className="rounded-full bg-accent px-3 py-1 text-sm font-medium text-accent-foreground">
                {cartUnits} items
              </div>
            </div>

            {!cart.length ? (
              <div className="mt-6 rounded-lg border border-dashed border-border bg-background/70 p-8 text-center">
                <ShoppingBasket className="mx-auto h-10 w-10 text-muted-foreground" />
                <p className="mt-4 text-lg font-medium">Cart is empty</p>
                <p className="mt-2 text-sm text-muted-foreground">Add products from the catalog lane or scan a barcode to start a sale.</p>
              </div>
            ) : (
              <div className="mt-5 space-y-3">
                {cart.map((line) => (
                  <div key={line.product_id} className="rounded-lg border border-border bg-background/85 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{line.name}</p>
                        <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">{line.sku}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setCart((prev) => removeProductFromCart(prev, line.product_id))}
                        aria-label={`Remove ${line.name} from cart`}
                        className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>

                    <div className="mt-4 flex items-center justify-between gap-3">
                      <div className="inline-flex items-center rounded-md border border-border bg-card">
                        <button
                          type="button"
                          onClick={() => setCart((prev) => updateCartLineQuantity(prev, line.product_id, line.quantity - 1))}
                          aria-label={`Decrease quantity for ${line.name}`}
                          className="rounded-l-2xl px-4 py-3 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                        >
                          <Minus className="h-4 w-4" />
                        </button>
                        <span aria-label={`${line.name} quantity`} className="min-w-14 px-3 text-center text-lg font-semibold">
                          {line.quantity}
                        </span>
                        <button
                          type="button"
                          onClick={() => setCart((prev) => updateCartLineQuantity(prev, line.product_id, line.quantity + 1))}
                          disabled={line.quantity >= line.stock_qty}
                          aria-label={`Increase quantity for ${line.name}`}
                          className="rounded-r-2xl px-4 py-3 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:text-muted-foreground/40"
                        >
                          <Plus className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="text-right">
                        <p className="text-sm text-muted-foreground">{formatCurrency(line.unit_price)} each</p>
                        <p className="text-lg font-semibold">{formatCurrency(line.unit_price * line.quantity)}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-6 rounded-lg border border-border bg-background/70 p-4">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-base font-semibold">Customer mode</h3>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                Make the cashier choice explicit instead of hiding it in one select box.
              </p>

              <div className="mt-4 grid gap-3">
                <CustomerModeButton
                  active={customerMode === 'guest'}
                  icon={UserRound}
                  label="Guest"
                  detail="Fastest path for walk-up checkout."
                  onClick={() => {
                    setCustomerMode('guest');
                    setSelectedCustomerId('');
                    setCustomerName('');
                    setCheckoutError(null);
                  }}
                />
                <CustomerModeButton
                  active={customerMode === 'existing'}
                  icon={Users}
                  label="Existing customer"
                  detail="Attach the sale to an existing customer record."
                  onClick={() => {
                    setCustomerMode('existing');
                    setCustomerName('');
                    setCheckoutError(null);
                  }}
                />
                <CustomerModeButton
                  active={customerMode === 'new'}
                  icon={Receipt}
                  label="New customer name"
                  detail="Capture a customer name on the sale without leaving the register."
                  onClick={() => {
                    setCustomerMode('new');
                    setSelectedCustomerId('');
                    setCheckoutError(null);
                  }}
                />
              </div>

              {customerMode === 'existing' ? (
                <div className="mt-4">
                  <label className="mb-2 block text-sm font-medium" htmlFor="pos-existing-customer">
                    Existing customer
                  </label>
                  <select
                    id="pos-existing-customer"
                    value={selectedCustomerId}
                    onChange={(event) => {
                      setSelectedCustomerId(event.target.value);
                      setCheckoutError(null);
                    }}
                    aria-label="Existing customer"
                    className="min-h-14 w-full rounded-md border border-input bg-background px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="">Select customer</option>
                    {customers.map((customer) => (
                      <option key={customer.id} value={customer.id}>
                        {customer.name}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}

              {customerMode === 'new' ? (
                <div className="mt-4">
                  <label className="mb-2 block text-sm font-medium" htmlFor="pos-customer-name">
                    Customer name
                  </label>
                  <input
                    id="pos-customer-name"
                    value={customerName}
                    onChange={(event) => setCustomerName(event.target.value)}
                    placeholder="Name for receipt or follow-up"
                    aria-label="Customer name"
                    className="min-h-14 w-full rounded-md border border-input bg-background px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              ) : null}
            </div>

            <div className="mt-4 rounded-lg border border-border bg-background/70 p-4">
              <div className="flex items-center gap-2">
                <WalletCards className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-base font-semibold">Payment method</h3>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {POS_PAYMENT_METHODS.map((method) => (
                  <PaymentButton
                    key={method.value}
                    active={paymentMethod === method.value}
                    label={method.label}
                    onClick={() => setPaymentMethod(method.value)}
                  />
                ))}
              </div>
              <div className="sr-only" aria-live="polite">
                Payment method: {POS_PAYMENT_METHODS.find((method) => method.value === paymentMethod)?.label || paymentMethod}
              </div>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium" htmlFor="pos-tax-collected">
                  Tax collected
                </label>
                <input
                  id="pos-tax-collected"
                  type="number"
                  min="0"
                  step="0.01"
                  value={taxCollected}
                  onChange={(event) => setTaxCollected(Math.max(0, Number(event.target.value) || 0))}
                  aria-label="Tax collected"
                  className="min-h-14 w-full rounded-md border border-input bg-background px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium" htmlFor="pos-notes">
                  Notes
                </label>
                <textarea
                  id="pos-notes"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  rows={3}
                  placeholder="Optional booth or counter notes"
                  aria-label="Notes"
                  className="w-full rounded-md border border-input bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>

            <div className="mt-4 rounded-lg bg-background p-4">
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

            <Button
              type="button"
              onClick={handleCheckout}
              disabled={
                saving ||
                !cart.length ||
                (customerMode === 'existing' && !selectedCustomerId) ||
                (customerMode === 'new' && !customerName.trim())
              }
              size="lg"
              className="mt-6 min-h-14 w-full font-semibold"
            >
              {saving ? 'Processing checkout...' : 'Complete checkout'}
            </Button>

            {!!cart.length ? (
              <button
                type="button"
                onClick={resetCheckoutFields}
                className="mt-3 inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-md border border-border px-4 py-3 font-semibold transition-colors hover:bg-accent"
              >
                <XCircle className="h-4 w-4" />
                Clear cart
              </button>
            ) : null}

            <div className="mt-4 rounded-md border border-amber-300/60 bg-amber-50 p-3 text-sm text-amber-900">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <p>Checkout blocks oversell when requested quantity exceeds available stock.</p>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Clock3 className="h-5 w-5 text-muted-foreground" />
                  <h2 className="text-xl font-semibold">Sales inbox</h2>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Recent sales and exceptions stay adjacent to the register so staff do not need to context-switch into the full sales area.
                </p>
              </div>
              <Link
                to="/sell/sales"
                className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm font-semibold text-foreground no-underline transition-colors hover:bg-accent"
              >
                Open inbox
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            {salesInboxLoading ? (
              <div className="mt-4 space-y-3">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div key={index} className="h-28 animate-pulse rounded-lg border border-border bg-background" />
                ))}
              </div>
            ) : salesInbox.length ? (
              <div className="mt-4 space-y-3">
                {salesInbox.map((sale) => (
                  <SalesInboxCard key={sale.id} sale={sale} />
                ))}
              </div>
            ) : (
              <EmptyState
                icon="sales"
                title="No recent sales"
                description="Completed sales will appear here so staff can review them without leaving the Sell workspace."
                className="py-10"
              />
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
