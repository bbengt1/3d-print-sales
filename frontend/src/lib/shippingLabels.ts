type ShippingLabelFields = {
  customer_name?: string | null;
  shipping_recipient_name?: string | null;
  shipping_address_line1?: string | null;
  shipping_city?: string | null;
  shipping_state?: string | null;
  shipping_postal_code?: string | null;
  shipping_country?: string | null;
  shipping_label_print_count?: number | null;
};

function hasValue(value: string | null | undefined) {
  return Boolean(value?.trim());
}

export function getShippingLabelMissingFields(sale: ShippingLabelFields) {
  const missing: string[] = [];
  if (!hasValue(sale.shipping_recipient_name) && !hasValue(sale.customer_name)) {
    missing.push('recipient name');
  }
  if (!hasValue(sale.shipping_address_line1)) {
    missing.push('address line 1');
  }
  if (!hasValue(sale.shipping_city)) {
    missing.push('city');
  }
  if (!hasValue(sale.shipping_state)) {
    missing.push('state');
  }
  if (!hasValue(sale.shipping_postal_code)) {
    missing.push('postal code');
  }
  if (!hasValue(sale.shipping_country)) {
    missing.push('country');
  }
  return missing;
}

export function getShippingLabelActionLabel(sale: ShippingLabelFields) {
  return (sale.shipping_label_print_count || 0) > 0 ? 'Reprint 4x6 Label' : 'Print 4x6 Label';
}
