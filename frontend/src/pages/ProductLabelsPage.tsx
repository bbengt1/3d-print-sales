import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Printer } from 'lucide-react';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import TableToolbar from '@/components/data/TableToolbar';
import SearchInput from '@/components/data/SearchInput';
import Pagination from '@/components/data/Pagination';
import { Button } from '@/components/ui/Button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import EmptyState from '@/components/ui/EmptyState';
import ProductLabel from '@/components/labels/ProductLabel';
import { printProductLabels } from '@/lib/printLabels';
import { useLabelSettings } from '@/hooks/useLabelSettings';
import { formatCurrency } from '@/lib/utils';
import type { BarcodeFormat } from '@/lib/barcode';
import type { PaginatedProducts, Product } from '@/types';

export default function ProductLabelsPage() {
  const labelSettings = useLabelSettings();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [formatOverride, setFormatOverride] = useState<BarcodeFormat | null>(null);
  const [includePrice, setIncludePrice] = useState<boolean | null>(null);

  const { data, isLoading } = useQuery<PaginatedProducts>({
    queryKey: ['products', 'labels', search, page, pageSize],
    queryFn: () =>
      api
        .get('/products', {
          params: {
            search: search || undefined,
            skip: page * pageSize,
            limit: pageSize,
            is_active: true,
          },
        })
        .then((r) => r.data),
  });

  const products = data?.items || [];
  const total = data?.total || 0;
  const productMap = useMemo(() => new Map(products.map((p) => [p.id, p])), [products]);
  const selectedProducts = useMemo(
    () => Array.from(selected).map((id) => productMap.get(id)).filter(Boolean) as Product[],
    [selected, productMap],
  );

  const activeFormat = formatOverride ?? labelSettings.defaultFormat;
  const activeIncludePrice = includePrice ?? labelSettings.includePrice;

  const handlePrintSheet = () => {
    if (!selectedProducts.length) return;
    printProductLabels(selectedProducts, {
      format: activeFormat,
      includePrice: activeIncludePrice,
      sheet: true,
    });
  };

  const previewProducts = selectedProducts.slice(0, 30);

  const columns: Column<Product>[] = [
    { key: 'name', header: 'Product', cell: (p) => <span className="font-medium">{p.name}</span> },
    { key: 'sku', header: 'SKU', cell: (p) => <span className="font-mono text-xs">{p.sku}</span> },
    {
      key: 'upc',
      header: 'UPC',
      colClassName: 'hidden md:table-cell',
      cell: (p) =>
        p.upc ? <span className="font-mono text-xs">{p.upc}</span> : <span className="text-muted-foreground">—</span>,
    },
    {
      key: 'unit_price',
      header: 'Price',
      numeric: true,
      cell: (p) => formatCurrency(p.unit_price),
    },
    {
      key: 'stock_qty',
      header: 'Stock',
      numeric: true,
      colClassName: 'hidden md:table-cell',
      cell: (p) => p.stock_qty,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Print labels"
        description={
          selected.size
            ? `${selected.size} ${selected.size === 1 ? 'product' : 'products'} selected`
            : 'Select products below to build a printable label sheet.'
        }
        actions={
          <Button onClick={handlePrintSheet} disabled={!selected.size}>
            <Printer className="h-4 w-4" />
            {selected.size ? `Print sheet (${selected.size})` : 'Print sheet'}
          </Button>
        }
      />

      <section className="space-y-3 rounded-md border border-border bg-card p-5 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold">Label settings</h2>
          <Tabs
            value={activeFormat}
            onValueChange={(v) => setFormatOverride(v as BarcodeFormat)}
          >
            <TabsList>
              <TabsTrigger value="code128">Code128</TabsTrigger>
              <TabsTrigger value="upc">UPC</TabsTrigger>
              <TabsTrigger value="qr">QR</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={activeIncludePrice}
            onChange={(e) => setIncludePrice(e.target.checked)}
            className="h-4 w-4 cursor-pointer rounded border-input accent-primary"
          />
          Include price on each label
        </label>
        <p className="text-xs text-muted-foreground">
          Sheet layout is Avery 5160 (30 labels, 2.625 × 1 in). Use Admin → Settings to change the default format or price display for new prints.
        </p>
      </section>

      <DataTable<Product>
        data={products}
        columns={columns}
        rowKey={(p) => p.id}
        selectable
        selected={selected}
        onSelectedChange={setSelected}
        loading={isLoading}
        emptyState="No active products found."
        toolbar={
          <TableToolbar total={total}>
            <SearchInput
              value={search}
              onChange={(v) => {
                setSearch(v);
                setPage(0);
              }}
              placeholder="Search products…"
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

      {previewProducts.length ? (
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold">Preview ({previewProducts.length} of {selected.size})</h2>
            {selected.size > 30 ? (
              <p className="text-xs text-muted-foreground">Showing first 30 selections.</p>
            ) : null}
          </div>
          <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6">
            {previewProducts.map((p) => (
              <ProductLabel
                key={p.id}
                product={p}
                format={activeFormat}
                includePrice={activeIncludePrice}
                variant="compact"
              />
            ))}
          </div>
        </section>
      ) : (
        <EmptyState
          compact
          icon="products"
          title="No labels previewed yet."
          description="Pick products from the list above to see them on an Avery 5160-style sheet."
        />
      )}
    </div>
  );
}
