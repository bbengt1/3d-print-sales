import { describe, expect, it } from 'vitest';
import { getShippingLabelActionLabel, getShippingLabelMissingFields } from '@/lib/shippingLabels';

describe('shipping label helpers', () => {
  it('reports all missing shipment fields required for printing', () => {
    expect(
      getShippingLabelMissingFields({
        customer_name: null,
        shipping_recipient_name: null,
        shipping_address_line1: '',
        shipping_city: '',
        shipping_state: '',
        shipping_postal_code: '',
        shipping_country: '',
      })
    ).toEqual([
      'recipient name',
      'address line 1',
      'city',
      'state',
      'postal code',
      'country',
    ]);
  });

  it('treats subsequent prints as reprints', () => {
    expect(getShippingLabelActionLabel({ shipping_label_print_count: 0 })).toBe('Print 4x6 Label');
    expect(getShippingLabelActionLabel({ shipping_label_print_count: 2 })).toBe('Reprint 4x6 Label');
  });
});
