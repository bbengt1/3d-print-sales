import type { POSCheckoutPayload, Product } from '@/types';

export const POS_PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'card', label: 'Card' },
  { value: 'venmo', label: 'Venmo' },
  { value: 'paypal', label: 'PayPal' },
  { value: 'other', label: 'Other' },
] as const;

export interface POSCartLine {
  product_id: string;
  name: string;
  sku: string;
  quantity: number;
  unit_price: number;
  unit_cost: number;
  stock_qty: number;
}

interface POSCheckoutBuildInput {
  cart: POSCartLine[];
  date: string;
  customerId: string;
  customerName?: string | null;
  taxCollected: number;
  paymentMethod: string;
  notes: string;
}

export function getProductCartQuantity(cart: POSCartLine[], productId: string): number {
  return cart.find((line) => line.product_id === productId)?.quantity ?? 0;
}

export function addProductToCart(cart: POSCartLine[], product: Product): POSCartLine[] {
  const existing = cart.find((line) => line.product_id === product.id);
  if (existing) {
    return cart.map((line) =>
      line.product_id === product.id
        ? {
            ...line,
            quantity: Math.min(line.quantity + 1, product.stock_qty),
            stock_qty: product.stock_qty,
          }
        : line
    );
  }

  return [
    ...cart,
    {
      product_id: product.id,
      name: product.name,
      sku: product.sku,
      quantity: 1,
      unit_price: Number(product.unit_price),
      unit_cost: Number(product.unit_cost),
      stock_qty: product.stock_qty,
    },
  ];
}

export function updateCartLineQuantity(
  cart: POSCartLine[],
  productId: string,
  nextQuantity: number,
): POSCartLine[] {
  return cart.flatMap((line) => {
    if (line.product_id !== productId) {
      return [line];
    }

    if (nextQuantity <= 0) {
      return [];
    }

    return [
      {
        ...line,
        quantity: Math.max(1, Math.min(nextQuantity, line.stock_qty)),
      },
    ];
  });
}

export function removeProductFromCart(cart: POSCartLine[], productId: string): POSCartLine[] {
  return cart.filter((line) => line.product_id !== productId);
}

export function getCartSubtotal(cart: POSCartLine[]): number {
  return cart.reduce((sum, line) => sum + line.quantity * line.unit_price, 0);
}

export function getCartTotal(cart: POSCartLine[], taxCollected: number): number {
  return getCartSubtotal(cart) + Math.max(0, taxCollected);
}

export function buildPOSCheckoutPayload({
  cart,
  date,
  customerId,
  customerName,
  taxCollected,
  paymentMethod,
  notes,
}: POSCheckoutBuildInput): POSCheckoutPayload {
  return {
    date,
    customer_id: customerId || null,
    customer_name: customerId ? null : customerName || null,
    tax_collected: Math.max(0, taxCollected),
    payment_method: paymentMethod,
    notes: notes.trim() || null,
    items: cart.map((line) => ({
      product_id: line.product_id,
      description: line.name,
      quantity: line.quantity,
      unit_price: line.unit_price,
      unit_cost: line.unit_cost,
    })),
  };
}
