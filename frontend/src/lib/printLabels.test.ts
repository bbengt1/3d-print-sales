import { afterEach, describe, expect, it, vi } from 'vitest';
import { printProductLabels } from './printLabels';
import { fetchBarcodeDataUrl } from '@/lib/barcode';
import type { Product } from '@/types';

vi.mock('@/lib/barcode', () => ({
  canRenderUpcA: (value: string | null | undefined) => /^\d{12}$/.test((value || '').trim()),
  fetchBarcodeDataUrl: vi.fn(),
}));

function createPrintWindow() {
  const state = { html: '' };
  return {
    state,
    printWindow: {
      opener: {},
      document: {
        readyState: 'complete',
        images: [],
        open: vi.fn(),
        write: vi.fn((html: string) => {
          state.html = html;
        }),
        close: vi.fn(),
      },
      addEventListener: vi.fn(),
      focus: vi.fn(),
      print: vi.fn(),
      requestAnimationFrame: vi.fn((cb: FrameRequestCallback) => {
        cb(0);
        return 1;
      }),
      setTimeout: vi.fn((cb: () => void) => {
        cb();
        return 1;
      }),
    } as unknown as Window,
  };
}

const product = {
  id: 'product-1',
  name: 'Calibration Cube',
  sku: 'CUBE-001',
  unit_price: 4.5,
} as Product;

describe('printProductLabels', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('opens the popup before waiting for barcode rendering', async () => {
    const { printWindow, state } = createPrintWindow();
    const open = vi.spyOn(window, 'open').mockReturnValue(printWindow);
    let resolveBarcode!: (value: string) => void;
    vi.mocked(fetchBarcodeDataUrl).mockReturnValue(
      new Promise((resolve) => {
        resolveBarcode = resolve;
      }),
    );

    const printPromise = printProductLabels([product], { format: 'code128', includePrice: true });

    expect(open).toHaveBeenCalledWith('', '_blank', 'width=800,height=900');
    expect(state.html).toContain('Preparing labels...');

    resolveBarcode('data:image/png;base64,barcode');
    await printPromise;

    expect(state.html).toContain('Calibration Cube');
    expect(state.html).toContain('CUBE-001');
    expect(state.html).toContain('data:image/png;base64,barcode');
    expect(state.html).toContain('$4.50');
  });

  it('renders sheet labels into the existing popup', async () => {
    const { printWindow, state } = createPrintWindow();
    vi.spyOn(window, 'open').mockReturnValue(printWindow);
    vi.mocked(fetchBarcodeDataUrl).mockResolvedValue('data:image/png;base64,barcode');

    await printProductLabels([product], { format: 'qr', sheet: true });

    expect(state.html).toContain('<div class="sheet">');
    expect(state.html).toContain('Calibration Cube');
  });

  it('shows an inline UPC requirement instead of fetching UPC images without a saved UPC', async () => {
    const { printWindow, state } = createPrintWindow();
    vi.spyOn(window, 'open').mockReturnValue(printWindow);

    await printProductLabels([{ ...product, upc: null }], { format: 'upc' });

    expect(fetchBarcodeDataUrl).not.toHaveBeenCalled();
    expect(state.html).toContain('UPC-A labels need a saved 12-digit UPC');
  });
});
