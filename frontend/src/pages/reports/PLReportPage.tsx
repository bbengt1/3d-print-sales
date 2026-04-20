import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Legend } from 'recharts';
import api from '@/api/client';
import { formatCurrency, formatPercent } from '@/lib/utils';
import ReportControls from '@/components/ui/ReportControls';
import { SkeletonTable } from '@/components/ui/Skeleton';
import DataTable from '@/components/data/DataTable';
import { KPIStrip, KPI } from '@/components/layout/KPIStrip';
import { Callout } from '@/components/ui/Callout';
import { ChartTooltip, chartCategoricalPalette } from '@/components/charts/ChartTooltip';
import type { PLReport, PLRow } from '@/types';

const formatTooltipCurrency = (value: string | number | readonly (string | number)[] | undefined) => {
  const normalized = Array.isArray(value) ? value[0] : value;
  return formatCurrency(Number(normalized ?? 0));
};

export default function PLReportPage() {
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [period, setPeriod] = useState('monthly');

  const { data, isLoading } = useQuery<PLReport>({
    queryKey: ['report', 'pl', dateFrom, dateTo, period],
    queryFn: () =>
      api
        .get('/reports/pl', {
          params: {
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            period,
          },
        })
        .then((r) => r.data),
  });

  const s = data?.summary;

  return (
    <div>
      <h2 className="text-base font-semibold mb-6">Profit & Loss</h2>

      <ReportControls
        dateFrom={dateFrom}
        dateTo={dateTo}
        period={period}
        csvUrl="/reports/pl/csv"
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onPeriodChange={setPeriod}
      />

      {isLoading ? (
        <SkeletonTable rows={5} cols={4} />
      ) : !data || !s ? null : (
        <div className="space-y-8">
          {/* Summary cards */}
          <KPIStrip columns={4}>
            <KPI
              label="Realized sales revenue"
              value={formatCurrency(s.total_revenue)}
              sub={`Sales basis only: ${formatCurrency(s.sales_revenue)}`}
            />
            <KPI label="Total costs" value={formatCurrency(s.total_costs)} />
            <KPI
              label="Gross profit"
              value={formatCurrency(s.gross_profit)}
              tone={s.gross_profit >= 0 ? 'success' : 'destructive'}
            />
            <KPI
              label="Profit margin"
              value={formatPercent(s.profit_margin_pct)}
              tone={s.profit_margin_pct >= 0 ? 'success' : 'destructive'}
            />
          </KPIStrip>

          <Callout tone="warning" title="Reporting basis: sales-realized revenue">
            <p>{s.production_estimate_note}</p>
            <p className="mt-1">Operational production estimate shown separately: {formatCurrency(s.operational_production_estimate)}</p>
          </Callout>

          {/* Cost breakdown */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-base font-semibold mb-4">Cost Breakdown</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              {[
                { label: 'Materials', value: s.material_costs },
                { label: 'Labor', value: s.labor_costs },
                { label: 'Machine', value: s.machine_costs },
                { label: 'Overhead', value: s.overhead_costs },
                { label: 'Platform Fees', value: s.platform_fees },
                { label: 'Shipping', value: s.shipping_costs },
              ].map(({ label, value }) => (
                <div key={label} className="text-center">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="text-lg font-semibold mt-1">{formatCurrency(value)}</p>
                  {s.total_costs > 0 && (
                    <p className="text-xs text-muted-foreground">{((value / s.total_costs) * 100).toFixed(0)}%</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Trend chart */}
          {data.period_data.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-6">
              <h3 className="text-base font-semibold mb-4">P&L Trend</h3>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={data.period_data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="period" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                  <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                  <ChartTooltip formatter={formatTooltipCurrency} />
                  <Legend />
                  <Bar dataKey="sales_revenue" name="Sales Revenue" stackId="rev" fill={chartCategoricalPalette[0]} />
                  <Bar dataKey="operational_production_estimate" name="Operational Production Estimate" fill={chartCategoricalPalette[2]} />
                  <Bar dataKey="material_costs" name="Materials" stackId="cost" fill="#f87171" />
                  <Bar dataKey="labor_costs" name="Labor" stackId="cost" fill="#fb923c" />
                  <Bar dataKey="machine_costs" name="Machine" stackId="cost" fill="#fbbf24" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Period table */}
          {data.period_data.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-base font-semibold">Period Detail</h3>
              <DataTable<PLRow>
                data={data.period_data}
                rowKey={(row) => row.period}
                columns={[
                  {
                    key: 'period',
                    header: 'Period',
                    cell: (row) => <span className="font-medium">{row.period}</span>,
                  },
                  {
                    key: 'sales_revenue',
                    header: 'Sales Rev',
                    numeric: true,
                    cell: (row) => formatCurrency(row.sales_revenue),
                  },
                  {
                    key: 'operational_production_estimate',
                    header: 'Prod Estimate',
                    numeric: true,
                    cell: (row) => (
                      <span className="text-muted-foreground">
                        {formatCurrency(row.operational_production_estimate)}
                      </span>
                    ),
                  },
                  {
                    key: 'material_costs',
                    header: 'Materials',
                    numeric: true,
                    cell: (row) => formatCurrency(row.material_costs),
                  },
                  {
                    key: 'labor_costs',
                    header: 'Labor',
                    numeric: true,
                    cell: (row) => formatCurrency(row.labor_costs),
                  },
                  {
                    key: 'machine_costs',
                    header: 'Machine',
                    numeric: true,
                    cell: (row) => formatCurrency(row.machine_costs),
                  },
                  {
                    key: 'overhead_costs',
                    header: 'Overhead',
                    numeric: true,
                    cell: (row) => formatCurrency(row.overhead_costs),
                  },
                  {
                    key: 'platform_fees',
                    header: 'Fees',
                    numeric: true,
                    cell: (row) => formatCurrency(row.platform_fees),
                  },
                  {
                    key: 'gross_profit',
                    header: 'Gross Profit',
                    numeric: true,
                    cell: (row) => (
                      <span
                        className={`font-semibold ${
                          row.gross_profit >= 0
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-destructive'
                        }`}
                      >
                        {formatCurrency(row.gross_profit)}
                      </span>
                    ),
                  },
                ]}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
