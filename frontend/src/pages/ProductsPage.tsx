import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Archive, ArchiveRestore, Eye, Pencil, Plus, ScanBarcode } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column, type SortDir } from '@/components/data/DataTable';
import StatusBadge from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import SearchInput from '@/components/data/SearchInput';
import Pagination from '@/components/data/Pagination';
import { Button } from '@/components/ui/Button';
import { formatCurrency } from '@/lib/utils';
import type { PaginatedProducts, Product } from '@/types';

export default function ProductsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<string>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  const { data, isLoading, refetch } = useQuery<PaginatedProducts>({
    queryKey: ['products', search, sortKey, sortDir, page, pageSize],
    queryFn: () =>
      api
        .get('/products', {
          params: {
            search: search || undefined,
            sort_by: sortKey || undefined,
            sort_dir: sortDir,
            skip: page * pageSize,
            limit: pageSize,
          },
        })
        .then((r) => r.data),
  });

  const products = data?.items || [];
  const total = data?.total || 0;
  const lowStockCount = products.filter((p) => p.stock_qty <= p.reorder_point).length;

  const toggleActive = async (product: Product) => {
    const action = product.is_active ? 'archive' : 'restore';
    const confirmed = window.confirm(
      product.is_active
        ? `Archive ${product.name}?\n\nThis removes it from active selling while preserving history.`
        : `Restore ${product.name} to active products?`,
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

  const handleSortChange = (key: string, dir: SortDir | null) => {
    if (!key || !dir) {
      setSortKey('name');
      setSortDir('asc');
    } else {
      setSortKey(key);
      setSortDir(dir);
    }
    setPage(0);
  };

  const activeFilters = [search].filter(Boolean).length;
  const clearFilters = () => {
    setSearch('');
    setPage(0);
  };

  const columns: Column<Product>[] = [
    { key: 'sku', header: 'SKU', sortable: true, cell: (p) => <span className="font-mono text-xs">{p.sku}</span> },
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      cell: (p) => (
        <div>
          <div className="font-medium">{p.name}</div>
          <div className="text-xs text-muted-foreground">{p.upc ? `UPC ${p.upc}` : 'No UPC yet'}</div>
        </div>
      ),
    },
    {
      key: 'unit_price',
      header: 'Price',
      sortable: true,
      numeric: true,
      cell: (p) => formatCurrency(p.unit_price),
    },
    {
      key: 'unit_cost',
      header: 'Cost',
      sortable: true,
      numeric: true,
      colClassName: 'hidden lg:table-cell',
      cell: (p) => formatCurrency(p.unit_cost),
    },
    {
      key: 'stock_qty',
      header: 'Stock',
      sortable: true,
      numeric: true,
      cell: (p) => {
        const low = p.stock_qty <= p.reorder_point;
        return (
          <span className={low ? 'text-amber-600 dark:text-amber-400' : ''}>
            {low ? <AlertTriangle className="mr-1 inline h-3 w-3" /> : null}
            {p.stock_qty}
          </span>
        );
      },
    },
    {
      key: 'readiness',
      header: 'Readiness',
      colClassName: 'hidden lg:table-cell',
      cell: (p) => (
        <div className="flex flex-wrap gap-1.5">
          <StatusBadge tone={p.is_active ? 'success' : 'neutral'}>{p.is_active ? 'Active' : 'Archived'}</StatusBadge>
          <StatusBadge tone={p.upc ? 'info' : 'neutral'}>
            {p.upc ? (
              <>
                <ScanBarcode className="mr-0.5 h-3 w-3" />
                POS
              </>
            ) : (
              'Manual'
            )}
          </StatusBadge>
        </div>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '112px',
      cell: (p) => (
        <div className="flex items-center justify-end gap-1">
          <Link
            to={`/product-studio/products/${p.id}/edit`}
            aria-label={`Edit ${p.name}`}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Pencil className="h-4 w-4" />
          </Link>
          <Link
            to={`/product-studio/products/${p.id}`}
            aria-label={`View ${p.name}`}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Eye className="h-4 w-4" />
          </Link>
          <button
            type="button"
            onClick={() => toggleActive(p)}
            aria-label={p.is_active ? `Archive ${p.name}` : `Restore ${p.name}`}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {p.is_active ? <Archive className="h-4 w-4" /> : <ArchiveRestore className="h-4 w-4" />}
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Products"
        description={
          <>
            <span className="tabular-nums">{total.toLocaleString()} total</span>
            {lowStockCount > 0 ? (
              <span className="ml-3 text-amber-600 dark:text-amber-400">· {lowStockCount} low stock</span>
            ) : null}
          </>
        }
        actions={
          <Button asChild>
            <Link to="/product-studio/products/new">
              <Plus className="h-4 w-4" />
              New product
            </Link>
          </Button>
        }
      />

      {/* Desktop table */}
      <div className="hidden md:block">
        <DataTable<Product>
          data={products}
          columns={columns}
          rowKey={(p) => p.id}
          sortKey={sortKey}
          sortDir={sortDir}
          onSortChange={handleSortChange}
          loading={isLoading}
          emptyState={
            activeFilters > 0
              ? 'No products match this search.'
              : 'No products yet — start in the product editor.'
          }
          toolbar={
            <TableToolbar
              total={total}
              activeFilters={activeFilters}
              onClearFilters={clearFilters}
            >
              <SearchInput
                value={search}
                onChange={(v) => {
                  setSearch(v);
                  setPage(0);
                }}
                placeholder="Search by name, SKU, or UPC…"
              />
            </TableToolbar>
          }
          footer={
            <Pagination
              page={page}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              onPageSizeChange={(n) => {
                setPageSize(n);
                setPage(0);
              }}
            />
          }
        />
      </div>

      {/* Mobile cards */}
      <div className="space-y-3 md:hidden">
        {products.map((product) => (
          <div key={product.id} className="rounded-md border border-border bg-card p-4 shadow-xs">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{product.name}</p>
                <p className="font-mono text-xs text-muted-foreground">{product.sku}</p>
              </div>
              <StatusBadge tone={product.is_active ? 'success' : 'neutral'}>
                {product.is_active ? 'Active' : 'Archived'}
              </StatusBadge>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Price</p>
                <p className="tabular-nums">{formatCurrency(product.unit_price)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Cost</p>
                <p className="tabular-nums">{formatCurrency(product.unit_cost)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Stock</p>
                <p
                  className={
                    product.stock_qty <= product.reorder_point
                      ? 'tabular-nums text-amber-600 dark:text-amber-400'
                      : 'tabular-nums'
                  }
                >
                  {product.stock_qty}
                </p>
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <Button asChild className="flex-1">
                <Link to={`/product-studio/products/${product.id}/edit`}>
                  <Pencil className="h-4 w-4" />
                  Edit
                </Link>
              </Button>
              <button
                type="button"
                onClick={() => navigate(`/product-studio/products/${product.id}`)}
                aria-label={`View ${product.name}`}
                className="inline-flex h-12 w-12 items-center justify-center rounded-md border border-border text-foreground"
              >
                <Eye className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
