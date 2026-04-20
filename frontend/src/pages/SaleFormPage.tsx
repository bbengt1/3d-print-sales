import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
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

  const inputCls =
    'w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring';

  return (
    <div>
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate('/sales')} className="p-2 hover:bg-accent rounded-md text-muted-foreground cursor-pointer">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-3xl font-bold">New Sale</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sale details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Header info */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Sale Details</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Date *</label>
                <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Status</label>
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className={inputCls}>
                  {['pending', 'paid', 'shipped', 'delivered'].map((s) => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Customer</label>
                <input
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
                  className={inputCls}
                />
                <datalist id="customer-list">
                  {customers?.map((c) => (
                    <option key={c.id} value={c.name} />
                  ))}
                </datalist>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Sales Channel</label>
                <select value={form.channel_id} onChange={(e) => setForm({ ...form, channel_id: e.target.value })} className={inputCls}>
                  <option value="">Direct Sale</option>
                  {channels?.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Payment Method</label>
                <select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })} className={inputCls}>
                  <option value="card">Card</option>
                  <option value="cash">Cash</option>
                  <option value="paypal">PayPal</option>
                  <option value="venmo">Venmo</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Tracking Number</label>
                <input value={form.tracking_number} onChange={(e) => setForm({ ...form, tracking_number: e.target.value })} placeholder="Optional" className={inputCls} />
              </div>
            </div>
            <div className="mt-4">
              <label className="block text-sm font-medium mb-1">Notes</label>
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} className={inputCls} />
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Shipment Label</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Recipient</label>
                <input value={form.shipping_recipient_name} onChange={(e) => setForm({ ...form, shipping_recipient_name: e.target.value })} placeholder="Customer or recipient name" className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Company</label>
                <input value={form.shipping_company} onChange={(e) => setForm({ ...form, shipping_company: e.target.value })} placeholder="Optional" className={inputCls} />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium mb-1">Address Line 1</label>
                <input value={form.shipping_address_line1} onChange={(e) => setForm({ ...form, shipping_address_line1: e.target.value })} placeholder="Street address" className={inputCls} />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium mb-1">Address Line 2</label>
                <input value={form.shipping_address_line2} onChange={(e) => setForm({ ...form, shipping_address_line2: e.target.value })} placeholder="Apartment, suite, etc. (optional)" className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">City</label>
                <input value={form.shipping_city} onChange={(e) => setForm({ ...form, shipping_city: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">State / Region</label>
                <input value={form.shipping_state} onChange={(e) => setForm({ ...form, shipping_state: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Postal Code</label>
                <input value={form.shipping_postal_code} onChange={(e) => setForm({ ...form, shipping_postal_code: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Country</label>
                <input value={form.shipping_country} onChange={(e) => setForm({ ...form, shipping_country: e.target.value })} className={inputCls} />
              </div>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              The backend produces a browser-printable 4x6 label, and the local workstation handles the thermal printer itself.
            </p>
          </div>

          {/* Line items */}
          <div className="bg-card border border-border rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Line Items</h2>
              <button onClick={addItem} className="inline-flex items-center gap-1 text-sm text-primary hover:opacity-80 cursor-pointer">
                <Plus className="w-4 h-4" /> Add Item
              </button>
            </div>
            <div className="space-y-4">
              {items.map((item, idx) => (
                <div key={idx} className="grid grid-cols-12 gap-2 items-end">
                  <div className="col-span-12 sm:col-span-3">
                    <label className="block text-xs text-muted-foreground mb-1">Product</label>
                    <select
                      value={item.product_id}
                      onChange={(e) => selectProduct(idx, e.target.value)}
                      className="w-full px-2 py-2 border border-input rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="">Custom item...</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-12 sm:col-span-3">
                    <label className="block text-xs text-muted-foreground mb-1">Description *</label>
                    <input value={item.description} onChange={(e) => updateItem(idx, { description: e.target.value })} className="w-full px-2 py-2 border border-input rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
                  </div>
                  <div className="col-span-4 sm:col-span-1">
                    <label className="block text-xs text-muted-foreground mb-1">Qty</label>
                    <input type="number" min="1" value={item.quantity} onChange={(e) => updateItem(idx, { quantity: Math.max(1, Number(e.target.value)) })} className="w-full px-2 py-2 border border-input rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
                  </div>
                  <div className="col-span-4 sm:col-span-2">
                    <label className="block text-xs text-muted-foreground mb-1">Price ($)</label>
                    <input type="number" step="0.01" min="0" value={item.unit_price} onChange={(e) => updateItem(idx, { unit_price: Number(e.target.value) })} className="w-full px-2 py-2 border border-input rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
                  </div>
                  <div className="col-span-3 sm:col-span-2">
                    <label className="block text-xs text-muted-foreground mb-1">Cost ($)</label>
                    <input type="number" step="0.01" min="0" value={item.unit_cost} onChange={(e) => updateItem(idx, { unit_cost: Number(e.target.value) })} className="w-full px-2 py-2 border border-input rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
                  </div>
                  <div className="col-span-1 flex justify-end">
                    <button onClick={() => removeItem(idx)} disabled={items.length === 1} className="p-2 hover:bg-accent rounded-md text-muted-foreground disabled:opacity-30 cursor-pointer">
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
            <h2 className="text-lg font-semibold mb-4">Shipping & Tax</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Shipping Charged</label>
                <input type="number" step="0.01" min="0" value={form.shipping_charged} onChange={(e) => setForm({ ...form, shipping_charged: Number(e.target.value) })} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Shipping Cost</label>
                <input type="number" step="0.01" min="0" value={form.shipping_cost} onChange={(e) => setForm({ ...form, shipping_cost: Number(e.target.value) })} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Tax Collected</label>
                <input type="number" step="0.01" min="0" value={form.tax_collected} onChange={(e) => setForm({ ...form, tax_collected: Number(e.target.value) })} className={inputCls} />
              </div>
            </div>
          </div>

          {/* Order Total */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Order Total</h2>
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
