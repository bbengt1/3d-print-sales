import { useEffect, useState } from 'react';
import { cn, formatCurrency } from '@/lib/utils';
import { canRenderUpcA, fetchBarcodeObjectUrl, type BarcodeFormat } from '@/lib/barcode';
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

    if (format === 'upc' && !canRenderUpcA(product.upc)) {
      setError('UPC-A labels need a saved 12-digit UPC. Generate one or switch to Code128.');
      return () => {
        cancelled = true;
      };
    }

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
