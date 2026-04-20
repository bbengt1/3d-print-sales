import api from '@/api/client';

export type BarcodeFormat = 'code128' | 'upc' | 'qr';

export interface BarcodeOptions {
  format?: BarcodeFormat;
  size?: number;
  /** When format=qr, encode the public product URL instead of UPC/SKU. */
  url?: boolean;
}

/** Build the relative URL (uses client baseURL) for direct <img src> use. */
export function buildBarcodeUrl(productId: string, opts: BarcodeOptions = {}): string {
  const params = new URLSearchParams();
  if (opts.format) params.set('format', opts.format);
  if (opts.size) params.set('size', String(opts.size));
  if (opts.url) params.set('url', '1');
  const qs = params.toString();
  return `/products/${productId}/barcode${qs ? `?${qs}` : ''}`;
}

/**
 * Fetch a barcode PNG as a blob object URL. Callers are responsible for
 * revoking the URL when the component unmounts (use the returned object
 * with `URL.revokeObjectURL` on cleanup).
 */
export async function fetchBarcodeObjectUrl(
  productId: string,
  opts: BarcodeOptions = {},
): Promise<string> {
  const resp = await api.get(buildBarcodeUrl(productId, opts), {
    responseType: 'blob',
  });
  return URL.createObjectURL(resp.data as Blob);
}

/**
 * Fetch a barcode PNG as a self-contained data URL. Useful when the
 * image needs to render in a separate window (print popup) that can't
 * inherit the caller's auth state.
 */
export async function fetchBarcodeDataUrl(
  productId: string,
  opts: BarcodeOptions = {},
): Promise<string> {
  const resp = await api.get(buildBarcodeUrl(productId, opts), {
    responseType: 'blob',
  });
  const blob = resp.data as Blob;
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}
