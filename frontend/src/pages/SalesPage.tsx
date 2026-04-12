import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Plus, Eye } from 'lucide-react';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import { SkeletonTable } from '@/components/ui/Skeleton';
import EmptyState from '@/components/ui/EmptyState';
import type { PaginatedSales, SalesChannel } from '@/types';

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  paid: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  shipped: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  delivered: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
  refunded: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
};

const defaultPaymentMethods = ['cash', 'card', 'other'];

export default function SalesPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [channelId, setChannelId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('');
  const [page, setPage] = useState(0);
  const limit = 25;

  const { data, isLoading } = useQuery<PaginatedSales>({
    queryKey: ['sales', search, status, channelId, paymentMethod, page],
    queryFn: () =>
      api
        .get('/sales', {
          params: {
            search: search || undefined,
            status: status || undefined,
            channel_id: channelId || undefined,
            payment_method: paymentMethod || undefined,
            skip: page * limit,
            limit,
          },
        })
        .then((r) => r.data),
  });
  const { data: channels } = useQuery<SalesChannel[]>({
    queryKey: ['sales-channels'],
    queryFn: () => api.get('/sales/channels').then((r) => r.data),
  });
  const sales = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);
  const paymentMethods = Array.from(
    new Set([
      ...defaultPaymentMethods,
      ...sales.map((sale) => sale.payment_method).filter(Boolean),
    ])
  ) as string[];

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-border bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.14),_transparent_24%),linear-gradient(135deg,_rgba(8,17,31,1),_rgba(16,33,52,0.98)_48%,_rgba(22,44,64,0.96)_100%)] p-6 text-white shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm uppercase tracking-[0.3em] text-white/65">Sell Workspace</p>
            <h1 className="mt-3 text-3xl font-bold">Sales inbox</h1>
            <p className="mt-3 text-sm text-white/80">
              Review recent sales, refunds, and follow-up work without dropping back into the general dashboard.
            </p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/8 px-4 py-4">
            <p className="text-xs uppercase tracking-[0.22em] text-white/60">Visible sales</p>
            <p className="mt-2 text-2xl font-semibold">{total}</p>
            <p className="mt-1 text-sm text-white/65">Filtered transactions in the current inbox view</p>
          </div>
        </div>
      </section>

      <div className="flex items-center justify-between">
        <Link
          to="/sell/sales/new"
          className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity no-underline"
        >
          <Plus className="w-4 h-4" /> New Sale
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          placeholder="Search by sale # or customer..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          className="w-full max-w-xs px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(0);
          }}
          className="px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All statuses</option>
          {['pending', 'paid', 'shipped', 'delivered', 'refunded', 'cancelled'].map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>
        <select
          value={channelId}
          onChange={(e) => {
            setChannelId(e.target.value);
            setPage(0);
          }}
          className="px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All channels</option>
          {channels?.map((channel) => (
            <option key={channel.id} value={channel.id}>
              {channel.name}
            </option>
          ))}
        </select>
        <select
          value={paymentMethod}
          onChange={(e) => {
            setPaymentMethod(e.target.value);
            setPage(0);
          }}
          className="px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All payment methods</option>
          {paymentMethods.map((method) => (
            <option key={method} value={method}>
              {method}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <SkeletonTable rows={5} cols={7} />
      ) : !sales.length ? (
        <EmptyState
          icon="default"
          title="No sales yet"
          description="Record your first sale to start tracking revenue."
          action={
            <Link
              to="/sell/sales/new"
              className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 no-underline"
            >
              <Plus className="w-4 h-4" /> New Sale
            </Link>
          }
        />
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto bg-card border border-border rounded-lg">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Sale #</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Customer</th>
                  <th className="px-4 py-3 font-medium">Channel</th>
                  <th className="px-4 py-3 font-medium">Payment</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium text-right">Total</th>
                  <th className="px-4 py-3 font-medium text-right">Contribution Margin</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sales.map((s) => (
                  <tr key={s.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                    <td className="px-4 py-3 font-mono text-xs">{s.sale_number}</td>
                    <td className="px-4 py-3">{s.date}</td>
                    <td className="px-4 py-3">{s.customer_name || '—'}</td>
                    <td className="px-4 py-3">{s.channel_name || 'Direct'}</td>
                    <td className="px-4 py-3 capitalize">{s.payment_method || '—'}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[s.status] || statusColors.pending}`}
                      >
                        {s.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">{formatCurrency(s.total)}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={Number(s.contribution_margin) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                        {formatCurrency(s.contribution_margin)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/sell/sales/${s.id}`} className="p-1.5 hover:bg-accent rounded-md text-muted-foreground inline-block" title="View">
                        <Eye className="w-4 h-4" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {sales.map((s) => (
              <Link key={s.id} to={`/sell/sales/${s.id}`} className="block bg-card border border-border rounded-lg p-4 no-underline">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-semibold">{s.sale_number}</p>
                    <p className="text-xs text-muted-foreground">{s.date} &middot; {s.customer_name || 'No customer'}</p>
                  </div>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[s.status] || statusColors.pending}`}>
                    {s.status}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Total</p>
                    <p>{formatCurrency(s.total)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Contribution</p>
                    <p className={Number(s.contribution_margin) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                      {formatCurrency(s.contribution_margin)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Payment</p>
                    <p className="capitalize">{s.payment_method || '—'}</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-3">{s.channel_name || 'Direct'} &middot; {s.item_count} items</p>
              </Link>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-muted-foreground">{total} sales</p>
              <div className="flex gap-2">
                <button disabled={page === 0} onClick={() => setPage(page - 1)} className="px-3 py-1 border border-border rounded-md text-sm hover:bg-accent disabled:opacity-50 cursor-pointer">
                  Prev
                </button>
                <span className="px-3 py-1 text-sm">
                  {page + 1} / {totalPages}
                </span>
                <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)} className="px-3 py-1 border border-border rounded-md text-sm hover:bg-accent disabled:opacity-50 cursor-pointer">
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
