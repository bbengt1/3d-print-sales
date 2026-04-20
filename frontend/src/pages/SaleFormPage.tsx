import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Label } from '@/components/ui/Label';
import PageHeader from '@/components/layout/PageHeader';
import { formatCurrency } from '@/lib/utils';
import type { SalesChannel, PaginatedProducts, Customer } from '@/types';

interface LineItem {
  product_id: string;
  description: string;
  quantity: number;
  unit_price: number;
  unit_cost: number;
}

const emptyItem: LineItem = { product_id: '', description: '', quantity: 1, unit_price: 0, unit_cost: 0 };

export default function SaleFormPage() {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    date: new Date().toISOString().split('T')[0],
    customer_name: '',
    channel_id: '',
    status: 'paid',
    payment_method: 'card',
    shipping_charged: 0,
    shipping_cost: 0,
    tax_collected: 0,
    tracking_number: '',
    shipping_recipient_name: '',
    shipping_company: '',
    shipping_address_line1: '',
    shipping_address_line2: '',
    shipping_city: '',
    shipping_state: '',
    shipping_postal_code: '',
    shipping_country: 'US',
    notes: '',
  });

  const [items, setItems] = useState<LineItem[]>([{ ...emptyItem }]);

  const { data: channels } = useQuery<SalesChannel[]>({
    queryKey: ['sales-channels'],
    queryFn: () => api.get('/sales/channels?is_active=true').then((r) => r.data),
  });

  const { data: productsData } = useQuery<PaginatedProducts>({
    queryKey: ['products', 'all'],
    queryFn: () => api.get('/products', { params: { limit: 100 } }).then((r) => r.data),
  });

  const { data: customers } = useQuery<Customer[]>({
    queryKey: ['customers'],
    queryFn: () => api.get('/customers').then((r) => r.data),
  });

  const products = productsData?.items || [];

  const updateItem = (index: number, updates: Partial<LineItem>) => {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...updates } : item)));
  };

  const selectProduct = (index: number, productId: string) => {
    const product = products.find((p) => p.id === productId);
    if (product) {
      updateItem(index, {
        product_id: product.id,
        description: product.name,
        unit_price: Number(product.unit_price),
        unit_cost: Number(product.unit_cost),
      });
    } else {
      updateItem(index, { product_id: '' });
    }
  };

  const addItem = () => setItems((prev) => [...prev, { ...emptyItem }]);
  const removeItem = (index: number) => {
    if (items.length > 1) setItems((prev) => prev.filter((_, i) => i !== index));
  };

  const subtotal = items.reduce((sum, i) => sum + i.unit_price * i.quantity, 0);
  const total = subtotal + form.shipping_charged + form.tax_collected;

  const save = async () => {
    if (!items.some((i) => i.description.trim())) {
      toast.error('Add at least one item with a description');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        channel_id: form.channel_id || null,
        tracking_number: form.tracking_number || null,
        shipping_recipient_name: form.shipping_recipient_name || null,
        shipping_company: form.shipping_company || null,
        shipping_address_line1: form.shipping_address_line1 || null,
        shipping_address_line2: form.shipping_address_line2 || null,
        shipping_city: form.shipping_city || null,
        shipping_state: form.shipping_state || null,
        shipping_postal_code: form.shipping_postal_code || null,
        shipping_country: form.shipping_country || null,
        notes: form.notes || null,
        items: items
          .filter((i) => i.description.trim())
          .map((i) => ({
            product_id: i.product_id || null,
            description: i.description,
            quantity: i.quantity,
            unit_price: i.unit_price,
            unit_cost: i.unit_cost,
          })),
      };
      const resp = await api.post('/sales', payload);
      toast.success('Sale created');
      navigate(`/sales/${resp.data.id}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create sale');
    } finally {
      setSaving(false);
    }
  };

  const selectCls =
    'flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring';

  return (
    <div className="space-y-6">
      <PageHeader
        title="New Sale"
        description="Record a sale, its line items, shipment destination, and totals."
        actions={
          <Button type="button" variant="outline" onClick={() => navigate('/sales')}>
            <ArrowLeft className="h-4 w-4" /> Back to sales
          </Button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sale details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Header info */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-base font-semibold mb-4">Sale Details</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="sale-date">Date *</Label>
                <Input id="sale-date" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-status">Status</Label>
                <select id="sale-status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className={selectCls}>
                  {['pending', 'paid', 'shipped', 'delivered'].map((s) => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-customer">Customer</Label>
                <Input
                  id="sale-customer"
                  list="customer-list"
                  value={form.customer_name}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      customer_name: e.target.value,
                      shipping_recipient_name: prev.shipping_recipient_name || e.target.value,
                    }))
                  }
                  placeholder="Customer name..."
                />
                <datalist id="customer-list">
                  {customers?.map((c) => (
                    <option key={c.id} value={c.name} />
                  ))}
                </datalist>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-channel">Sales Channel</Label>
                <select id="sale-channel" value={form.channel_id} onChange={(e) => setForm({ ...form, channel_id: e.target.value })} className={selectCls}>
                  <option value="">Direct Sale</option>
                  {channels?.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-payment">Payment Method</Label>
                <select id="sale-payment" value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })} className={selectCls}>
                  <option value="card">Card</option>
                  <option value="cash">Cash</option>
                  <option value="paypal">PayPal</option>
                  <option value="venmo">Venmo</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-tracking">Tracking Number</Label>
                <Input id="sale-tracking" value={form.tracking_number} onChange={(e) => setForm({ ...form, tracking_number: e.target.value })} placeholder="Optional" />
              </div>
            </div>
            <div className="mt-4 space-y-1.5">
              <Label htmlFor="sale-notes">Notes</Label>
              <Textarea id="sale-notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} />
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-base font-semibold mb-4">Shipment Label</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="sale-ship-recipient">Recipient</Label>
                <Input id="sale-ship-recipient" value={form.shipping_recipient_name} onChange={(e) => setForm({ ...form, shipping_recipient_name: e.target.value })} placeholder="Customer or recipient name" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-ship-company">Company</Label>
                <Input id="sale-ship-company" value={form.shipping_company} onChange={(e) => setForm({ ...form, shipping_company: e.target.value })} placeholder="Optional" />
              </div>
              <div className="sm:col-span-2 space-y-1.5">
                <Label htmlFor="sale-ship-address1">Address Line 1</Label>
                <Input id="sale-ship-address1" value={form.shipping_address_line1} onChange={(e) => setForm({ ...form, shipping_address_line1: e.target.value })} placeholder="Street address" />
              </div>
              <div className="sm:col-span-2 space-y-1.5">
                <Label htmlFor="sale-ship-address2">Address Line 2</Label>
                <Input id="sale-ship-address2" value={form.shipping_address_line2} onChange={(e) => setForm({ ...form, shipping_address_line2: e.target.value })} placeholder="Apartment, suite, etc. (optional)" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-ship-city">City</Label>
                <Input id="sale-ship-city" value={form.shipping_city} onChange={(e) => setForm({ ...form, shipping_city: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-ship-state">State / Region</Label>
                <Input id="sale-ship-state" value={form.shipping_state} onChange={(e) => setForm({ ...form, shipping_state: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-ship-postal">Postal Code</Label>
                <Input id="sale-ship-postal" value={form.shipping_postal_code} onChange={(e) => setForm({ ...form, shipping_postal_code: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-ship-country">Country</Label>
                <Input id="sale-ship-country" value={form.shipping_country} onChange={(e) => setForm({ ...form, shipping_country: e.target.value })} />
              </div>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              The backend produces a browser-printable 4x6 label, and the local workstation handles the thermal printer itself.
            </p>
          </div>

          {/* Line items */}
          <div className="bg-card border border-border rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold">Line Items</h2>
              <button onClick={addItem} className="inline-flex items-center gap-1 text-sm text-primary hover:opacity-80">
                <Plus className="w-4 h-4" /> Add Item
              </button>
            </div>
            <div className="space-y-4">
              {items.map((item, idx) => (
                <div key={idx} className="grid grid-cols-12 gap-2 items-end">
                  <div className="col-span-12 sm:col-span-3 space-y-1.5">
                    <Label htmlFor={`sale-item-${idx}-product`} className="text-xs text-muted-foreground">Product</Label>
                    <select
                      id={`sale-item-${idx}-product`}
                      value={item.product_id}
                      onChange={(e) => selectProduct(idx, e.target.value)}
                      className={selectCls}
                    >
                      <option value="">Custom item...</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-12 sm:col-span-3 space-y-1.5">
                    <Label htmlFor={`sale-item-${idx}-description`} className="text-xs text-muted-foreground">Description *</Label>
                    <Input id={`sale-item-${idx}-description`} value={item.description} onChange={(e) => updateItem(idx, { description: e.target.value })} />
                  </div>
                  <div className="col-span-4 sm:col-span-1 space-y-1.5">
                    <Label htmlFor={`sale-item-${idx}-qty`} className="text-xs text-muted-foreground">Qty</Label>
                    <Input id={`sale-item-${idx}-qty`} type="number" min="1" value={item.quantity} onChange={(e) => updateItem(idx, { quantity: Math.max(1, Number(e.target.value)) })} />
                  </div>
                  <div className="col-span-4 sm:col-span-2 space-y-1.5">
                    <Label htmlFor={`sale-item-${idx}-price`} className="text-xs text-muted-foreground">Price ($)</Label>
                    <Input id={`sale-item-${idx}-price`} type="number" step="0.01" min="0" value={item.unit_price} onChange={(e) => updateItem(idx, { unit_price: Number(e.target.value) })} />
                  </div>
                  <div className="col-span-3 sm:col-span-2 space-y-1.5">
                    <Label htmlFor={`sale-item-${idx}-cost`} className="text-xs text-muted-foreground">Cost ($)</Label>
                    <Input id={`sale-item-${idx}-cost`} type="number" step="0.01" min="0" value={item.unit_cost} onChange={(e) => updateItem(idx, { unit_cost: Number(e.target.value) })} />
                  </div>
                  <div className="col-span-1 flex justify-end">
                    <button onClick={() => removeItem(idx)} disabled={items.length === 1} className="p-2 hover:bg-accent rounded-md text-muted-foreground disabled:opacity-30">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Shipping & Tax */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-base font-semibold mb-4">Shipping & Tax</h2>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="sale-shipping-charged">Shipping Charged</Label>
                <Input id="sale-shipping-charged" type="number" step="0.01" min="0" value={form.shipping_charged} onChange={(e) => setForm({ ...form, shipping_charged: Number(e.target.value) })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-shipping-cost">Shipping Cost</Label>
                <Input id="sale-shipping-cost" type="number" step="0.01" min="0" value={form.shipping_cost} onChange={(e) => setForm({ ...form, shipping_cost: Number(e.target.value) })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sale-tax">Tax Collected</Label>
                <Input id="sale-tax" type="number" step="0.01" min="0" value={form.tax_collected} onChange={(e) => setForm({ ...form, tax_collected: Number(e.target.value) })} />
              </div>
            </div>
          </div>

          {/* Order Total */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-base font-semibold mb-4">Order Total</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Subtotal</span>
                <span>{formatCurrency(subtotal)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Shipping</span>
                <span>{formatCurrency(form.shipping_charged)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tax</span>
                <span>{formatCurrency(form.tax_collected)}</span>
              </div>
              <div className="flex justify-between font-semibold text-base border-t border-border pt-2">
                <span>Total</span>
                <span>{formatCurrency(total)}</span>
              </div>
            </div>
          </div>

          {/* Submit */}
          <Button onClick={save} disabled={saving} className="w-full">
            {saving ? 'Creating...' : 'Create Sale'}
          </Button>
        </div>
      </div>
    </div>
  );
}
