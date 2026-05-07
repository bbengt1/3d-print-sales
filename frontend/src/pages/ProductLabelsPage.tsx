import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Printer, WandSparkles } from 'lucide-react';
import { toast } from 'sonner';
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
import { canRenderUpcA, type BarcodeFormat } from '@/lib/barcode';
import { getApiErrorMessage } from '@/lib/apiError';
import type { PaginatedProducts, Product, ProductBarcodeGenerateResponse } from '@/types';

export default function ProductLabelsPage() {
  const queryClient = useQueryClient();
  const labelSettings = useLabelSettings();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [formatOverride, setFormatOverride] = useState<BarcodeFormat | null>(null);
  const [includePrice, setIncludePrice] = useState<boolean | null>(null);
  const [generatingUpcs, setGeneratingUpcs] = useState(false);

  const { data, isLoading, refetch } = useQuery<PaginatedProducts>({
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
  const selectedWithoutRenderableUpc = useMemo(
    () => selectedProducts.filter((product) => !canRenderUpcA(product.upc)),
    [selectedProducts],
  );
  const upcPrintBlocked = activeFormat === 'upc' && selectedWithoutRenderableUpc.length > 0;

  const handlePrintSheet = async () => {
    if (!selectedProducts.length) return;
    if (upcPrintBlocked) {
      toast.error('Generate UPCs for the selected products before printing UPC-A labels.');
      return;
    }
    try {
      await printProductLabels(selectedProducts, {
        format: activeFormat,
        includePrice: activeIncludePrice,
        sheet: true,
      });
    } catch (err) {
      toast.error((err as Error)?.message || 'Failed to open label sheet');
    }
  };

  const handleGenerateUpcs = async () => {
    if (!selectedWithoutRenderableUpc.length) return;

    setGeneratingUpcs(true);
    try {
      for (const product of selectedWithoutRenderableUpc) {
        const response = await api.post<ProductBarcodeGenerateResponse>('/products/barcode/generate');
        await api.put(`/products/${product.id}`, { upc: response.data.upc });
      }

      await queryClient.invalidateQueries({ queryKey: ['products'] });
      await refetch();
      toast.success(
        `Generated UPC${selectedWithoutRenderableUpc.length === 1 ? '' : 's'} for ${selectedWithoutRenderableUpc.length} selected product${selectedWithoutRenderableUpc.length === 1 ? '' : 's'}`,
      );
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to generate UPCs for selected products'));
    } finally {
      setGeneratingUpcs(false);
    }
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
          <>
            {activeFormat === 'upc' && selectedWithoutRenderableUpc.length ? (
              <Button
                type="button"
                variant="outline"
                onClick={handleGenerateUpcs}
                disabled={generatingUpcs}
              >
                <WandSparkles className="h-4 w-4" />
                {generatingUpcs
                  ? 'Generating...'
                  : `Generate UPC${selectedWithoutRenderableUpc.length === 1 ? '' : 's'} (${selectedWithoutRenderableUpc.length})`}
              </Button>
            ) : null}
            <Button onClick={handlePrintSheet} disabled={!selected.size || upcPrintBlocked}>
              <Printer className="h-4 w-4" />
              {selected.size ? `Print sheet (${selected.size})` : 'Print sheet'}
            </Button>
          </>
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
        {upcPrintBlocked ? (
          <p className="text-xs font-medium text-warning">
            {selectedWithoutRenderableUpc.length} selected product{selectedWithoutRenderableUpc.length === 1 ? '' : 's'} need a saved 12-digit UPC before UPC-A labels can print.
          </p>
        ) : null}
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
