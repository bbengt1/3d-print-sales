import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ArrowRight, Archive, ArchiveRestore, Eye, Pencil, Plus, ScanBarcode } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import EmptyState from '@/components/ui/EmptyState';
import { SkeletonTable } from '@/components/ui/Skeleton';
import PageHeader from '@/components/layout/PageHeader';
import { formatCurrency } from '@/lib/utils';
import type { PaginatedProducts, Product } from '@/types';

export default function ProductsPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const limit = 25;

  const { data, isLoading, refetch } = useQuery<PaginatedProducts>({
    queryKey: ['products', search, page],
    queryFn: () =>
      api.get('/products', { params: { search: search || undefined, skip: page * limit, limit } }).then((r) => r.data),
  });

  const products = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const lowStockCount = products.filter((product) => product.stock_qty <= product.reorder_point).length;

  const toggleActive = async (product: Product) => {
    const action = product.is_active ? 'archive' : 'restore';
    const confirmed = window.confirm(
      product.is_active
        ? `Archive ${product.name}?\n\nThis removes it from active selling while preserving history.`
        : `Restore ${product.name} to active products?`
    );

    if (!confirmed) return;

    try {
      if (product.is_active) {
        await api.delete(`/products/${product.id}`);
        toast.success(`${product.name} archived`);
      } else {
        await api.put(`/products/${product.id}`, { is_active: true });
        toast.success(`${product.name} restored`);
      }
      await refetch();
    } catch {
      toast.error(`Failed to ${action} product`);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Products"
        description={
          <>
            <span className="tabular-nums">{total.toLocaleString()} total</span>
            {lowStockCount > 0 ? (
              <span className="ml-3 text-warning">
                · {lowStockCount} low stock
              </span>
            ) : null}
          </>
        }
        actions={
          <Link
            to="/product-studio/products/new"
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground no-underline transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            New product
          </Link>
        }
      />

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-xl font-semibold">Catalog</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Search products and jump to either the full-page editor or the existing detail record.
            </p>
          </div>
          <input
            placeholder="Search products by name or SKU..."
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(0);
            }}
            className="w-full rounded-md border border-input bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring lg:max-w-sm"
          />
        </div>
      </section>

      {isLoading ? (
        <SkeletonTable rows={5} cols={8} />
      ) : !products.length ? (
        <EmptyState
          icon="products"
          title="No products yet"
          description="Start the catalog in the new full-page product editor."
          action={
            <Link
              to="/product-studio/products/new"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground no-underline hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              New product
            </Link>
          }
        />
      ) : (
        <>
          <div className="hidden overflow-x-auto rounded-lg border border-border bg-card shadow-sm md:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">SKU</th>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium text-right">Price</th>
                  <th className="px-4 py-3 font-medium text-right">Cost</th>
                  <th className="px-4 py-3 font-medium text-right">Stock</th>
                  <th className="px-4 py-3 font-medium">Readiness</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((product) => {
                  const lowStock = product.stock_qty <= product.reorder_point;
                  return (
                    <tr key={product.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                      <td className="px-4 py-3 font-mono text-xs">{product.sku}</td>
                      <td className="px-4 py-3">
                        <div className="font-medium">{product.name}</div>
                        <div className="mt-0.5 text-xs text-muted-foreground">
                          {product.upc ? `UPC ${product.upc}` : 'No UPC yet'}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">{formatCurrency(product.unit_price)}</td>
                      <td className="px-4 py-3 text-right">{formatCurrency(product.unit_cost)}</td>
                      <td className="px-4 py-3 text-right">
                        <span className={lowStock ? 'text-amber-600 dark:text-amber-400' : ''}>
                          {lowStock ? <AlertTriangle className="mr-1 inline h-3 w-3" /> : null}
                          {product.stock_qty}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <span className="inline-flex items-center rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-foreground">
                            {product.is_active ? 'Active' : 'Archived'}
                          </span>
                          <span className="inline-flex items-center rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-foreground">
                            {product.upc ? (
                              <>
                                <ScanBarcode className="mr-1 h-3 w-3" />
                                POS ready
                              </>
                            ) : (
                              'Manual lookup'
                            )}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <Link
                            to={`/product-studio/products/${product.id}/edit`}
                            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent"
                            title="Edit in Product Studio"
                          >
                            <Pencil className="h-4 w-4" />
                          </Link>
                          <Link
                            to={`/product-studio/products/${product.id}`}
                            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent"
                            title="View detail"
                          >
                            <Eye className="h-4 w-4" />
                          </Link>
                          <button
                            type="button"
                            onClick={() => toggleActive(product)}
                            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent"
                            title={product.is_active ? 'Archive product' : 'Restore product'}
                          >
                            {product.is_active ? <Archive className="h-4 w-4" /> : <ArchiveRestore className="h-4 w-4" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="space-y-3 md:hidden">
            {products.map((product) => (
              <div key={product.id} className="rounded-lg border border-border bg-card p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{product.name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{product.sku}</p>
                  </div>
                  <span className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-foreground">
                    {product.is_active ? 'Active' : 'Archived'}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Price</p>
                    <p>{formatCurrency(product.unit_price)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Cost</p>
                    <p>{formatCurrency(product.unit_cost)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Stock</p>
                    <p className={product.stock_qty <= product.reorder_point ? 'text-amber-600 dark:text-amber-400' : ''}>
                      {product.stock_qty}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex gap-2">
                  <Link
                    to={`/product-studio/products/${product.id}/edit`}
                    className="inline-flex flex-1 items-center justify-center gap-2 rounded-md bg-primary px-4 py-3 font-semibold text-primary-foreground no-underline"
                  >
                    <Pencil className="h-4 w-4" />
                    Edit
                  </Link>
                  <Link
                    to={`/product-studio/products/${product.id}`}
                    className="inline-flex items-center justify-center rounded-md border border-border px-4 py-3 text-foreground no-underline"
                  >
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 ? (
            <div className="flex items-center justify-between text-sm">
              <p className="text-muted-foreground">{total} products</p>
              <div className="flex gap-2">
                <button
                  disabled={page === 0}
                  onClick={() => setPage(page - 1)}
                  className="rounded-md border border-border px-3 py-1 transition-colors hover:bg-accent disabled:opacity-50"
                >
                  Prev
                </button>
                <span className="px-3 py-1">
                  {page + 1} / {totalPages}
                </span>
                <button
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage(page + 1)}
                  className="rounded-md border border-border px-3 py-1 transition-colors hover:bg-accent disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
