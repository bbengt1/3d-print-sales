import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import ReportControls from '@/components/ui/ReportControls';
import { SkeletonTable } from '@/components/ui/Skeleton';
import DataTable from '@/components/data/DataTable';
import type { SalesReport, ProductRanking, ChannelBreakdown } from '@/types';

const formatTooltipCurrency = (value: string | number | readonly (string | number)[] | undefined) => {
  const normalized = Array.isArray(value) ? value[0] : value;
  return formatCurrency(Number(normalized ?? 0));
};

export default function SalesReportPage() {
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [period, setPeriod] = useState('monthly');

  const { data, isLoading } = useQuery<SalesReport>({
    queryKey: ['report', 'sales', dateFrom, dateTo, period],
    queryFn: () =>
      api
        .get('/reports/sales', {
          params: {
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            period,
          },
        })
        .then((r) => r.data),
  });

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Sales Report</h2>

      <ReportControls
        dateFrom={dateFrom}
        dateTo={dateTo}
        period={period}
        csvUrl="/reports/sales/csv"
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onPeriodChange={setPeriod}
      />

      {isLoading ? (
        <SkeletonTable rows={5} cols={5} />
      ) : !data ? null : (
        <div className="space-y-8">
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Total Orders</p>
              <p className="text-3xl font-bold mt-1">{data.total_orders}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Gross Sales</p>
              <p className="text-3xl font-bold mt-1">{formatCurrency(data.gross_sales)}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Item COGS</p>
              <p className="text-3xl font-bold mt-1">{formatCurrency(data.item_cogs)}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Gross Profit</p>
              <p className={`text-3xl font-bold mt-1 ${data.gross_profit >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {formatCurrency(data.gross_profit)}
              </p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Platform Fees + Shipping</p>
              <p className="text-3xl font-bold mt-1">{formatCurrency(data.platform_fees + data.shipping_costs)}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Contribution Margin</p>
              <p className={`text-3xl font-bold mt-1 ${data.contribution_margin >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {formatCurrency(data.contribution_margin)}
              </p>
            </div>
          </div>

          {/* Revenue over time chart */}
          {data.period_data.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Revenue Over Time</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={data.period_data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="period" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                  <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                  <Tooltip formatter={formatTooltipCurrency} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                  <Legend />
                  <Line type="monotone" dataKey="gross_sales" name="Gross Sales" stroke="var(--color-primary)" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="gross_profit" name="Gross Profit" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="contribution_margin" name="Contribution Margin" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top products */}
            {data.top_products.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-lg font-semibold">Top Products</h3>
                <DataTable<ProductRanking & { _idx: number }>
                  data={data.top_products.map((p, i) => ({ ...p, _idx: i }))}
                  rowKey={(p) => String(p._idx)}
                  columns={[
                    { key: 'description', header: 'Product', cell: (p) => p.description },
                    { key: 'units_sold', header: 'Units', numeric: true, cell: (p) => p.units_sold },
                    {
                      key: 'gross_sales',
                      header: 'Gross Sales',
                      numeric: true,
                      cell: (p) => formatCurrency(p.gross_sales),
                    },
                    {
                      key: 'contribution_margin',
                      header: 'Contribution',
                      numeric: true,
                      cell: (p) => (
                        <span
                          className={
                            p.contribution_margin >= 0
                              ? 'text-green-600 dark:text-green-400'
                              : 'text-red-600 dark:text-red-400'
                          }
                        >
                          {formatCurrency(p.contribution_margin)}
                        </span>
                      ),
                    },
                  ]}
                />
              </div>
            )}

            {/* Channel breakdown */}
            {data.channel_breakdown.length > 0 && (
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4">Channel Breakdown</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={data.channel_breakdown}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="channel_name" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                    <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                    <Tooltip formatter={formatTooltipCurrency} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                    <Legend />
                    <Bar dataKey="gross_sales" name="Gross Sales" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="contribution_margin" name="Contribution Margin" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-4">
                  <DataTable<ChannelBreakdown & { _idx: number }>
                    data={data.channel_breakdown.map((ch, i) => ({ ...ch, _idx: i }))}
                    rowKey={(ch) => String(ch._idx)}
                    columns={[
                      { key: 'channel_name', header: 'Channel', cell: (ch) => ch.channel_name },
                      { key: 'order_count', header: 'Orders', numeric: true, cell: (ch) => ch.order_count },
                      {
                        key: 'gross_sales',
                        header: 'Gross Sales',
                        numeric: true,
                        cell: (ch) => formatCurrency(ch.gross_sales),
                      },
                      {
                        key: 'gross_profit',
                        header: 'Gross Profit',
                        numeric: true,
                        cell: (ch) => formatCurrency(ch.gross_profit),
                      },
                      {
                        key: 'platform_fees',
                        header: 'Fees',
                        numeric: true,
                        cell: (ch) => (
                          <span className="text-muted-foreground">{formatCurrency(ch.platform_fees)}</span>
                        ),
                      },
                      {
                        key: 'shipping_costs',
                        header: 'Shipping',
                        numeric: true,
                        cell: (ch) => (
                          <span className="text-muted-foreground">{formatCurrency(ch.shipping_costs)}</span>
                        ),
                      },
                      {
                        key: 'contribution_margin',
                        header: 'Contribution',
                        numeric: true,
                        cell: (ch) => formatCurrency(ch.contribution_margin),
                      },
                    ]}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
