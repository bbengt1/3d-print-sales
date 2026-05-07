import { canRenderUpcA, fetchBarcodeDataUrl, type BarcodeFormat } from '@/lib/barcode';
import { openBlankPrintWindow, writePrintWindow } from '@/lib/printWindow';
import { formatCurrency } from '@/lib/utils';
import type { Product } from '@/types';

export interface PrintOptions {
  format: BarcodeFormat;
  includePrice?: boolean;
  /** Render a 30-up Avery 5160 sheet when true; single-label layout otherwise. */
  sheet?: boolean;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

async function renderLabelHtml(
  product: Product,
  format: BarcodeFormat,
  includePrice: boolean,
): Promise<string> {
  let imgTag = '';
  if (format === 'upc' && !canRenderUpcA(product.upc)) {
    imgTag = '<span class="err">UPC-A labels need a saved 12-digit UPC. Generate one or use Code128.</span>';
  } else {
    try {
      const dataUrl = await fetchBarcodeDataUrl(product.id, { format });
      imgTag = `<img src="${dataUrl}" alt="${escapeHtml(product.name)} ${format} barcode" />`;
    } catch (err) {
      imgTag = `<span class="err">${escapeHtml(
        (err as Error)?.message ?? 'Unable to render barcode',
      )}</span>`;
    }
  }
  const priceHtml = includePrice
    ? `<div class="price">${escapeHtml(formatCurrency(product.unit_price))}</div>`
    : '';
  return `
    <div class="label">
      <div class="name">${escapeHtml(product.name)}</div>
      <div class="sku">${escapeHtml(product.sku)}</div>
      ${imgTag}
      ${priceHtml}
    </div>
  `;
}

/**
 * Open a print-ready window with one or more product labels. For single
 * labels the popup is a centered card; for `sheet: true` it renders
 * a 30-up Avery 5160 grid.
 */
export async function printProductLabels(
  products: Product[],
  opts: PrintOptions,
): Promise<void> {
  if (!products.length) return;

  const printWindow = openBlankPrintWindow('Preparing labels');

  const html = await Promise.all(
    products.map((p) => renderLabelHtml(p, opts.format, opts.includePrice ?? false)),
  );

  if (opts.sheet) {
    writePrintWindow(
      printWindow,
      `Labels (${products.length})`,
      `<div class="sheet">${html.join('\n')}</div>`,
    );
    return;
  }

  const title = products[0]?.name ? `Label — ${products[0].name}` : 'Label';
  writePrintWindow(
    printWindow,
    title,
    `<h1>${escapeHtml(title)}</h1><div style="max-width: 360px; margin: 0 auto;">${html.join('\n')}</div>`,
  );
}
