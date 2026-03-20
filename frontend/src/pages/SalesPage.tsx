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

export default function SalesPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [channelId, setChannelId] = useState('');
  const [page, setPage] = useState(0);
  const limit = 25;

  const { data, isLoading } = useQuery<PaginatedSales>({
    queryKey: ['sales', search, status, channelId, page],
    queryFn: () =>
      api
        .get('/sales', {
          params: {
            search: search || undefined,
            status: status || undefined,
            channel_id: channelId || undefined,
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

  const channelMap = new Map(channels?.map((c) => [c.id, c.name]) || []);
  const sales = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Sales</h1>
        <Link
          to="/sales/new"
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
          {channels?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
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
              to="/sales/new"
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
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium text-right">Total</th>
                  <th className="px-4 py-3 font-medium text-right">Net Revenue</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sales.map((s) => (
                  <tr key={s.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                    <td className="px-4 py-3 font-mono text-xs">{s.sale_number}</td>
                    <td className="px-4 py-3">{s.date}</td>
                    <td className="px-4 py-3">{s.customer_name || '—'}</td>
                    <td className="px-4 py-3">{s.channel_id ? channelMap.get(s.channel_id) || '—' : 'Direct'}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[s.status] || statusColors.pending}`}
                      >
                        {s.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">{formatCurrency(s.total)}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={Number(s.net_revenue) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                        {formatCurrency(s.net_revenue)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/sales/${s.id}`} className="p-1.5 hover:bg-accent rounded-md text-muted-foreground inline-block" title="View">
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
              <Link key={s.id} to={`/sales/${s.id}`} className="block bg-card border border-border rounded-lg p-4 no-underline">
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
                    <p className="text-xs text-muted-foreground">Net</p>
                    <p className={Number(s.net_revenue) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                      {formatCurrency(s.net_revenue)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Items</p>
                    <p>{s.item_count}</p>
                  </div>
                </div>
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
