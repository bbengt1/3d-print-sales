import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Printer, RefreshCw, Save } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Callout } from '@/components/ui/Callout';
import PageHeader from '@/components/layout/PageHeader';
import Breadcrumbs from '@/components/ui/Breadcrumbs';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';
import { getShippingLabelActionLabel, getShippingLabelMissingFields } from '@/lib/shippingLabels';
import { formatCurrency } from '@/lib/utils';
import type { Sale, SalesChannel } from '@/types';

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [savingShipment, setSavingShipment] = useState(false);
  const [printingLabel, setPrintingLabel] = useState(false);
  const [markingPrinted, setMarkingPrinted] = useState(false);
  const [shipmentForm, setShipmentForm] = useState({
    shipping_recipient_name: '',
    shipping_company: '',
    shipping_address_line1: '',
    shipping_address_line2: '',
    shipping_city: '',
    shipping_state: '',
    shipping_postal_code: '',
    shipping_country: '',
    tracking_number: '',
  });

  const { data: sale, isLoading } = useQuery<Sale>({
    queryKey: ['sale', id],
    queryFn: () => api.get(`/sales/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: channels } = useQuery<SalesChannel[]>({
    queryKey: ['sales-channels'],
    queryFn: () => api.get('/sales/channels').then((r) => r.data),
  });

  useEffect(() => {
    if (!sale) {
      return;
    }
    setShipmentForm({
      shipping_recipient_name: sale.shipping_recipient_name || sale.customer_name || '',
      shipping_company: sale.shipping_company || '',
      shipping_address_line1: sale.shipping_address_line1 || '',
      shipping_address_line2: sale.shipping_address_line2 || '',
      shipping_city: sale.shipping_city || '',
      shipping_state: sale.shipping_state || '',
      shipping_postal_code: sale.shipping_postal_code || '',
      shipping_country: sale.shipping_country || '',
      tracking_number: sale.tracking_number || '',
    });
  }, [sale]);

  const channelName = sale?.channel_id
    ? channels?.find((c) => c.id === sale.channel_id)?.name || '—'
    : 'Direct';

  const handleStatusChange = async (newStatus: string) => {
    try {
      await api.put(`/sales/${id}`, { status: newStatus });
      await queryClient.invalidateQueries({ queryKey: ['sale', id] });
      toast.success(`Status updated to ${newStatus}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update');
    }
  };

  const handleRefund = async () => {
    try {
      await api.post(`/sales/${id}/refund`);
      await queryClient.invalidateQueries({ queryKey: ['sale', id] });
      toast.success('Sale refunded');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to refund');
    }
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/sales/${id}`);
      toast.success('Sale deleted');
      navigate('/sales');
    } catch {
      toast.error('Failed to delete');
    }
  };

  const handleShipmentSave = async () => {
    try {
      setSavingShipment(true);
      await api.put(`/sales/${id}`, {
        tracking_number: shipmentForm.tracking_number || null,
        shipping_recipient_name: shipmentForm.shipping_recipient_name || null,
        shipping_company: shipmentForm.shipping_company || null,
        shipping_address_line1: shipmentForm.shipping_address_line1 || null,
        shipping_address_line2: shipmentForm.shipping_address_line2 || null,
        shipping_city: shipmentForm.shipping_city || null,
        shipping_state: shipmentForm.shipping_state || null,
        shipping_postal_code: shipmentForm.shipping_postal_code || null,
        shipping_country: shipmentForm.shipping_country || null,
      });
      await queryClient.invalidateQueries({ queryKey: ['sale', id] });
      toast.success('Shipment details saved');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save shipment details');
    } finally {
      setSavingShipment(false);
    }
  };

  const handlePrintLabel = async () => {
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      toast.error('Popup blocked. Allow popups for this workstation to print labels.');
      return;
    }

    try {
      setPrintingLabel(true);
      const resp = await api.get(`/sales/${id}/shipping-label`, {
        responseType: 'text',
        headers: {
          Accept: 'text/html',
        },
      });

      printWindow.document.open();
      printWindow.document.write(resp.data as string);
      printWindow.document.close();
      printWindow.focus();
      window.setTimeout(() => {
        printWindow.print();
      }, 250);
      await queryClient.invalidateQueries({ queryKey: ['sale', id] });
      toast.success('Print dialog opened on this workstation. Mark the label printed after a successful thermal print.');
    } catch (err: any) {
      printWindow.close();
      toast.error(err.response?.data?.detail || 'Failed to open shipping label');
    } finally {
      setPrintingLabel(false);
    }
  };

  const handleMarkPrinted = async () => {
    try {
      setMarkingPrinted(true);
      await api.post(`/sales/${id}/shipping-label/mark-printed`);
      await queryClient.invalidateQueries({ queryKey: ['sale', id] });
      toast.success('Label marked as printed');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to mark label printed');
    } finally {
      setMarkingPrinted(false);
    }
  };

  if (isLoading) {
    return <div className="animate-pulse space-y-4"><div className="h-8 bg-muted rounded w-1/3" /><div className="h-64 bg-muted rounded" /></div>;
  }

  if (!sale) {
    return <div className="text-center py-16 text-muted-foreground">Sale not found</div>;
  }

  const shipmentMissingFields = getShippingLabelMissingFields({
    customer_name: shipmentForm.shipping_recipient_name ? null : sale.customer_name,
    shipping_recipient_name: shipmentForm.shipping_recipient_name,
    shipping_address_line1: shipmentForm.shipping_address_line1,
    shipping_city: shipmentForm.shipping_city,
    shipping_state: shipmentForm.shipping_state,
    shipping_postal_code: shipmentForm.shipping_postal_code,
    shipping_country: shipmentForm.shipping_country,
    shipping_label_print_count: sale.shipping_label_print_count,
  });

  const shipmentDirty =
    shipmentForm.shipping_recipient_name !== (sale.shipping_recipient_name || sale.customer_name || '') ||
    shipmentForm.shipping_company !== (sale.shipping_company || '') ||
    shipmentForm.shipping_address_line1 !== (sale.shipping_address_line1 || '') ||
    shipmentForm.shipping_address_line2 !== (sale.shipping_address_line2 || '') ||
    shipmentForm.shipping_city !== (sale.shipping_city || '') ||
    shipmentForm.shipping_state !== (sale.shipping_state || '') ||
    shipmentForm.shipping_postal_code !== (sale.shipping_postal_code || '') ||
    shipmentForm.shipping_country !== (sale.shipping_country || '') ||
    shipmentForm.tracking_number !== (sale.tracking_number || '');

  return (
    <div className="space-y-6">
      <PageHeader
        title={sale.sale_number}
        description={`${sale.date} · ${sale.customer_name || 'No customer'}`}
        breadcrumbs={
          <Breadcrumbs
            items={[
              { to: '/sell/sales', label: 'Sales' },
              { label: sale.sale_number },
            ]}
          />
        }
        actions={
          <div className="flex items-center gap-2">
            <Link
              to="/sales"
              className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-accent no-underline"
            >
              <ArrowLeft className="w-4 h-4" /> Back
            </Link>
            <StatusBadge tone={defaultStatusTone(sale.status)} className="text-sm">
              <span className="capitalize">{sale.status}</span>
            </StatusBadge>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Line Items</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="pb-2 font-medium">Description</th>
                <th className="pb-2 font-medium text-right">Qty</th>
                <th className="pb-2 font-medium text-right">Price</th>
                <th className="pb-2 font-medium text-right">Cost</th>
                <th className="pb-2 font-medium text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {sale.items.map((item) => (
                <tr key={item.id} className="border-b border-border last:border-0">
                  <td className="py-3">{item.description}</td>
                  <td className="py-3 text-right">{item.quantity}</td>
                  <td className="py-3 text-right">{formatCurrency(item.unit_price)}</td>
                  <td className="py-3 text-right text-muted-foreground">{formatCurrency(item.unit_cost)}</td>
                  <td className="py-3 text-right font-medium">{formatCurrency(item.line_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-6">
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Summary</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Subtotal</span><span>{formatCurrency(sale.subtotal)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Shipping charged</span><span>{formatCurrency(sale.shipping_charged)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Tax collected</span><span>{formatCurrency(sale.tax_collected)}</span></div>
              <div className="flex justify-between font-semibold border-t border-border pt-2"><span>Total</span><span>{formatCurrency(sale.total)}</span></div>
              <div className="flex justify-between text-muted-foreground"><span>Item COGS</span><span>-{formatCurrency(sale.item_cogs)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Gross Profit</span><span>{formatCurrency(sale.gross_profit)}</span></div>
              <div className="flex justify-between text-muted-foreground"><span>Platform fees</span><span>-{formatCurrency(sale.platform_fees)}</span></div>
              <div className="flex justify-between text-muted-foreground"><span>Shipping cost</span><span>-{formatCurrency(sale.shipping_cost)}</span></div>
              <div className={`flex justify-between font-semibold border-t border-border pt-2 ${Number(sale.contribution_margin) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>
                <span>Contribution Margin</span>
                <span>{formatCurrency(sale.contribution_margin)}</span>
              </div>
              <p className="text-xs text-muted-foreground pt-2 border-t border-border">Net profit is not shown yet because overhead allocation has not been implemented.</p>
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Details</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Channel</span><span>{channelName}</span></div>
              {sale.payment_method && <div className="flex justify-between"><span className="text-muted-foreground">Payment</span><span className="capitalize">{sale.payment_method}</span></div>}
              {sale.tracking_number && <div className="flex justify-between"><span className="text-muted-foreground">Tracking</span><span className="font-mono text-xs">{sale.tracking_number}</span></div>}
              {sale.notes && <div className="pt-2 border-t border-border"><p className="text-muted-foreground text-xs">Notes</p><p className="mt-1">{sale.notes}</p></div>}
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-6 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Shipping Label</h2>
                <p className="text-sm text-muted-foreground">
                  Server renders a 4x6 browser-printable label. The workstation browser owns the final thermal print step.
                </p>
              </div>
              <div className="text-right text-xs text-muted-foreground">
                <p>Format: {sale.shipping_label_format || 'html-4x6-v1'}</p>
                <p>Printed: {sale.shipping_label_print_count}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3">
              <Input value={shipmentForm.shipping_recipient_name} onChange={(e) => setShipmentForm((prev) => ({ ...prev, shipping_recipient_name: e.target.value }))} placeholder="Recipient name" />
              <Input value={shipmentForm.shipping_company} onChange={(e) => setShipmentForm((prev) => ({ ...prev, shipping_company: e.target.value }))} placeholder="Company (optional)" />
              <Input value={shipmentForm.shipping_address_line1} onChange={(e) => setShipmentForm((prev) => ({ ...prev, shipping_address_line1: e.target.value }))} placeholder="Address line 1" />
              <Input value={shipmentForm.shipping_address_line2} onChange={(e) => setShipmentForm((prev) => ({ ...prev, shipping_address_line2: e.target.value }))} placeholder="Address line 2" />
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Input value={shipmentForm.shipping_city} onChange={(e) => setShipmentForm((prev) => ({ ...prev, shipping_city: e.target.value }))} placeholder="City" />
                <Input value={shipmentForm.shipping_state} onChange={(e) => setShipmentForm((prev) => ({ ...prev, shipping_state: e.target.value }))} placeholder="State" />
                <Input value={shipmentForm.shipping_postal_code} onChange={(e) => setShipmentForm((prev) => ({ ...prev, shipping_postal_code: e.target.value }))} placeholder="Postal code" />
              </div>
              <Input value={shipmentForm.shipping_country} onChange={(e) => setShipmentForm((prev) => ({ ...prev, shipping_country: e.target.value }))} placeholder="Country" />
              <Input value={shipmentForm.tracking_number} onChange={(e) => setShipmentForm((prev) => ({ ...prev, tracking_number: e.target.value }))} placeholder="Tracking number" />
            </div>

            {shipmentMissingFields.length > 0 ? (
              <Callout tone="warning">
                Add {shipmentMissingFields.join(', ')} before printing from this workstation.
              </Callout>
            ) : (
              <Callout tone="success">
                Label is ready for workstation-local printing. Canceling the browser print dialog does not mark the label printed.
              </Callout>
            )}

            <div className="grid grid-cols-1 gap-2">
              <button
                onClick={handleShipmentSave}
                disabled={savingShipment || !shipmentDirty}
                className="inline-flex items-center justify-center gap-2 rounded-md border border-border px-4 py-2 hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Save className="w-4 h-4" /> {savingShipment ? 'Saving shipment...' : 'Save Shipment Details'}
              </button>
              <Button
                onClick={handlePrintLabel}
                disabled={printingLabel || shipmentMissingFields.length > 0 || shipmentDirty}
              >
                <Printer className="h-4 w-4" /> {printingLabel ? 'Opening print dialog...' : getShippingLabelActionLabel(sale)}
              </Button>
              <button
                onClick={handleMarkPrinted}
                disabled={markingPrinted || shipmentDirty || shipmentMissingFields.length > 0}
                className="rounded-md border border-border px-4 py-2 hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
              >
                {markingPrinted ? 'Recording print...' : 'Mark Printed After Successful Print'}
              </button>
            </div>

            <div className="text-xs text-muted-foreground">
              <p>Generated: {sale.shipping_label_generated_at ? new Date(sale.shipping_label_generated_at).toLocaleString() : 'Not generated yet'}</p>
              <p>Last printed: {sale.shipping_label_last_printed_at ? new Date(sale.shipping_label_last_printed_at).toLocaleString() : 'Not marked printed yet'}</p>
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-6 space-y-3">
            <h2 className="text-lg font-semibold mb-2">Actions</h2>
            {sale.status !== 'refunded' && sale.status !== 'cancelled' && (
              <select
                value={sale.status}
                onChange={(e) => handleStatusChange(e.target.value)}
                className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {['pending', 'paid', 'shipped', 'delivered'].map((s) => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
            )}
            {sale.status !== 'refunded' && sale.status !== 'cancelled' && (
              <button
                onClick={handleRefund}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-destructive text-destructive rounded-md hover:bg-destructive/10 cursor-pointer"
              >
                <RefreshCw className="w-4 h-4" /> Refund Sale
              </button>
            )}
            <button
              onClick={handleDelete}
              className="w-full px-4 py-2 border border-border text-muted-foreground rounded-md hover:bg-accent cursor-pointer"
            >
              Delete Sale
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
