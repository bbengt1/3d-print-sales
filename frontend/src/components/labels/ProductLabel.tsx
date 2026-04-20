import { useEffect, useState } from 'react';
import { cn, formatCurrency } from '@/lib/utils';
import { fetchBarcodeObjectUrl, type BarcodeFormat } from '@/lib/barcode';
import type { Product } from '@/types';

interface ProductLabelProps {
  product: Product;
  format: BarcodeFormat;
  includePrice?: boolean;
  /** Avery-5160 cell size is 2.625 × 1 in. Pass `compact` for sheet use. */
  variant?: 'preview' | 'compact';
  /** Optional className override on the outer card. */
  className?: string;
}

/**
 * Standalone printable product label. Renders name + SKU/UPC + barcode
 * (+ optional price). Styled to print cleanly inside an Avery 5160
 * cell when `variant="compact"`, or as a preview card otherwise.
 */
export default function ProductLabel({
  product,
  format,
  includePrice = false,
  variant = 'preview',
  className,
}: ProductLabelProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setError(null);
    setSrc(null);

    fetchBarcodeObjectUrl(product.id, { format, size: variant === 'compact' ? 2 : 3 })
      .then((url) => {
        objectUrl = url;
        if (!cancelled) setSrc(url);
      })
      .catch((err) => {
        if (!cancelled) {
          const detail = err?.response?.data;
          setError(
            typeof detail === 'string'
              ? detail
              : 'Unable to render this barcode format for this product.',
          );
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [product.id, format, variant]);

  const isCompact = variant === 'compact';

  return (
    <div
      className={cn(
        'label-card flex flex-col items-center justify-between gap-1 rounded-md border border-border bg-card text-center text-foreground',
        isCompact ? 'p-1 text-[0.6rem]' : 'p-4 text-sm',
        className,
      )}
    >
      <div className="w-full min-w-0">
        <p
          className={cn(
            'truncate font-semibold',
            isCompact ? 'text-[0.65rem] leading-tight' : 'text-sm',
          )}
          title={product.name}
        >
          {product.name}
        </p>
        <p
          className={cn(
            'truncate font-mono text-muted-foreground',
            isCompact ? 'text-[0.55rem]' : 'text-xs',
          )}
        >
          {product.sku}
        </p>
      </div>

      <div className={cn('flex w-full items-center justify-center', isCompact ? 'h-[0.9in]' : 'h-32')}>
        {error ? (
          <span className="text-[0.55rem] text-destructive">{error}</span>
        ) : src ? (
          <img
            src={src}
            alt={`${product.name} ${format} barcode`}
            className={cn('max-h-full max-w-full object-contain', format === 'qr' && 'aspect-square')}
          />
        ) : (
          <span className="text-[0.55rem] text-muted-foreground">Loading…</span>
        )}
      </div>

      {includePrice ? (
        <p
          className={cn(
            'font-semibold tabular-nums',
            isCompact ? 'text-[0.65rem]' : 'text-sm',
          )}
        >
          {formatCurrency(product.unit_price)}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Open a blank window and render `html` with a minimal print-friendly
 * stylesheet. Window auto-triggers `window.print()` once the content is
 * loaded; the user can choose their printer from the browser dialog.
 */
export function openPrintWindow(title: string, bodyHtml: string, extraCss = '') {
  const win = window.open('', '_blank', 'noopener,noreferrer,width=800,height=900');
  if (!win) return;
  win.document.open();
  win.document.write(`<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>${title}</title>
    <style>
      :root { color-scheme: light; }
      body { margin: 0; padding: 24px; font-family: ui-sans-serif, system-ui, sans-serif; color: #0f172a; background: #fff; }
      h1 { font-size: 14px; margin: 0 0 16px; }
      .label {
        display: flex; flex-direction: column; align-items: center; gap: 4px;
        border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; text-align: center;
      }
      .label .name { font-weight: 600; font-size: 12px; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .label .sku { font-family: ui-monospace, monospace; font-size: 10px; color: #475569; }
      .label .price { font-weight: 600; font-size: 12px; margin-top: 2px; }
      .label img { max-width: 100%; height: auto; }
      .sheet { display: grid; grid-template-columns: repeat(3, 2.625in); grid-auto-rows: 1in; gap: 0; border: 0; }
      .sheet .label { border: 1px dashed #e2e8f0; border-radius: 0; padding: 4px; gap: 2px; }
      .sheet .label .name { font-size: 9px; }
      .sheet .label .sku { font-size: 7px; }
      .sheet .label .price { font-size: 9px; }
      @media print {
        body { padding: 0; }
        h1 { display: none; }
        .label, .sheet .label { border-color: transparent; page-break-inside: avoid; }
      }
      ${extraCss}
    </style>
  </head>
  <body>
    ${bodyHtml}
    <script>
      window.addEventListener('load', () => {
        setTimeout(() => window.print(), 50);
      });
    </script>
  </body>
</html>`);
  win.document.close();
}
