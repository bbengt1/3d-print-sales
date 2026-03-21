import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import type { Sale, SalesChannel } from '@/types';

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  paid: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  shipped: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  delivered: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
  refunded: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
};

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: sale, isLoading } = useQuery<Sale>({
    queryKey: ['sale', id],
    queryFn: () => api.get(`/sales/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: channels } = useQuery<SalesChannel[]>({
    queryKey: ['sales-channels'],
    queryFn: () => api.get('/sales/channels').then((r) => r.data),
  });

  const channelName = sale?.channel_id
    ? channels?.find((c) => c.id === sale.channel_id)?.name || '—'
    : 'Direct';

  const handleStatusChange = async (newStatus: string) => {
    try {
      await api.put(`/sales/${id}`, { status: newStatus });
      queryClient.invalidateQueries({ queryKey: ['sale', id] });
      toast.success(`Status updated to ${newStatus}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update');
    }
  };

  const handleRefund = async () => {
    try {
      await api.post(`/sales/${id}/refund`);
      queryClient.invalidateQueries({ queryKey: ['sale', id] });
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

  if (isLoading) {
    return <div className="animate-pulse space-y-4"><div className="h-8 bg-muted rounded w-1/3" /><div className="h-64 bg-muted rounded" /></div>;
  }

  if (!sale) {
    return <div className="text-center py-16 text-muted-foreground">Sale not found</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-8">
        <Link to="/sales" className="p-2 hover:bg-accent rounded-md text-muted-foreground">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">{sale.sale_number}</h1>
          <p className="text-muted-foreground">{sale.date} &middot; {sale.customer_name || 'No customer'}</p>
        </div>
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusColors[sale.status] || statusColors.pending}`}>
          {sale.status}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Line Items */}
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

        {/* Summary & Actions */}
        <div className="space-y-6">
          {/* Financial summary */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Summary</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Subtotal</span><span>{formatCurrency(sale.subtotal)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Shipping charged</span><span>{formatCurrency(sale.shipping_charged)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Tax collected</span><span>{formatCurrency(sale.tax_collected)}</span></div>
              <div className="flex justify-between font-semibold border-t border-border pt-2"><span>Total</span><span>{formatCurrency(sale.total)}</span></div>
              <div className="flex justify-between text-muted-foreground"><span>Platform fees</span><span>-{formatCurrency(sale.platform_fees)}</span></div>
              <div className="flex justify-between text-muted-foreground"><span>Shipping cost</span><span>-{formatCurrency(sale.shipping_cost)}</span></div>
              <div className={`flex justify-between font-semibold border-t border-border pt-2 ${Number(sale.contribution_margin) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                <span>Contribution Margin</span>
                <span>{formatCurrency(sale.contribution_margin)}</span>
              </div>
            </div>
          </div>

          {/* Details */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Details</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Channel</span><span>{channelName}</span></div>
              {sale.payment_method && <div className="flex justify-between"><span className="text-muted-foreground">Payment</span><span className="capitalize">{sale.payment_method}</span></div>}
              {sale.tracking_number && <div className="flex justify-between"><span className="text-muted-foreground">Tracking</span><span className="font-mono text-xs">{sale.tracking_number}</span></div>}
              {sale.notes && <div className="pt-2 border-t border-border"><p className="text-muted-foreground text-xs">Notes</p><p className="mt-1">{sale.notes}</p></div>}
            </div>
          </div>

          {/* Actions */}
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
