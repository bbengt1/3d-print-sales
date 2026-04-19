import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Copy, Plus } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column, type SortDir } from '@/components/data/DataTable';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import SearchInput from '@/components/data/SearchInput';
import Select from '@/components/data/Select';
import Pagination from '@/components/data/Pagination';
import { formatCurrency } from '@/lib/utils';
import type { Job, PaginatedJobs } from '@/types';

const STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
];

export default function JobsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [sortKey, setSortKey] = useState<string>('date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery<PaginatedJobs>({
    queryKey: ['jobs', { search, status, sortKey, sortDir, page, pageSize }],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (status) params.set('status', status);
      if (sortKey) params.set('sort_by', sortKey);
      params.set('sort_dir', sortDir);
      params.set('skip', String(page * pageSize));
      params.set('limit', String(pageSize));
      return api.get(`/jobs?${params}`).then((r) => r.data);
    },
  });

  const jobs = data?.items || [];
  const total = data?.total || 0;

  const handleDuplicate = async (job: Job) => {
    setDuplicatingId(job.id);
    try {
      const { data } = await api.post(`/jobs/${job.id}/duplicate`);
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      toast.success('Job copied to draft successfully');
      navigate(`/orders/jobs/${data.id}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to copy job');
    } finally {
      setDuplicatingId(null);
    }
  };

  const handleSortChange = (key: string, dir: SortDir | null) => {
    if (!key || !dir) {
      setSortKey('date');
      setSortDir('desc');
    } else {
      setSortKey(key);
      setSortDir(dir);
    }
    setPage(0);
  };

  const activeFilters = [search, status].filter(Boolean).length;
  const clearFilters = () => {
    setSearch('');
    setStatus('');
    setPage(0);
  };

  const columns: Column<Job>[] = [
    {
      key: 'job_number',
      header: 'Job #',
      sortable: true,
      cell: (j) => (
        <Link to={`/orders/jobs/${j.id}`} className="font-mono text-xs font-medium text-primary no-underline hover:underline">
          {j.job_number}
        </Link>
      ),
    },
    { key: 'date', header: 'Date', sortable: true, cell: (j) => j.date },
    {
      key: 'customer_name',
      header: 'Customer',
      colClassName: 'hidden lg:table-cell',
      cell: (j) => j.customer_name || <span className="text-muted-foreground">—</span>,
    },
    { key: 'product_name', header: 'Product', cell: (j) => j.product_name },
    {
      key: 'printer',
      header: 'Printer',
      colClassName: 'hidden lg:table-cell',
      cell: (j) => <span className="text-xs text-muted-foreground">{j.printer?.name || '—'}</span>,
    },
    { key: 'total_pieces', header: 'Pieces', numeric: true, cell: (j) => j.total_pieces },
    {
      key: 'total_revenue',
      header: 'Revenue',
      sortable: true,
      numeric: true,
      cell: (j) => formatCurrency(j.total_revenue),
    },
    {
      key: 'net_profit',
      header: 'Profit',
      sortable: true,
      numeric: true,
      colClassName: 'hidden md:table-cell',
      cell: (j) => (
        <span className={j.net_profit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}>
          {formatCurrency(j.net_profit)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      cell: (j) => <StatusBadge tone={defaultStatusTone(j.status)}>{j.status.replace('_', ' ')}</StatusBadge>,
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '104px',
      cell: (j) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleDuplicate(j);
          }}
          disabled={duplicatingId === j.id}
          aria-label={`Copy ${j.job_number}`}
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border px-2.5 text-xs font-medium transition-colors hover:bg-muted disabled:opacity-50"
        >
          <Copy className="h-3.5 w-3.5" />
          {duplicatingId === j.id ? 'Copying…' : 'Copy'}
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Jobs"
        description={`${total.toLocaleString()} ${total === 1 ? 'job' : 'jobs'}`}
        actions={
          <Link
            to="/orders/jobs/new"
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground no-underline transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" /> New job
          </Link>
        }
      />

      <DataTable<Job>
        data={jobs}
        columns={columns}
        rowKey={(j) => j.id}
        onRowClick={(j) => navigate(`/orders/jobs/${j.id}`)}
        sortKey={sortKey}
        sortDir={sortDir}
        onSortChange={handleSortChange}
        loading={isLoading}
        emptyState={activeFilters > 0 ? 'No jobs match these filters.' : 'No jobs yet — create one to get started.'}
        toolbar={
          <TableToolbar total={total} activeFilters={activeFilters} onClearFilters={clearFilters}>
            <SearchInput
              value={search}
              onChange={(v) => {
                setSearch(v);
                setPage(0);
              }}
              placeholder="Search jobs…"
            />
            <Select
              value={status}
              onChange={(v) => {
                setStatus(v);
                setPage(0);
              }}
              options={STATUS_OPTIONS}
              placeholder="All statuses"
              aria-label="Filter by status"
            />
          </TableToolbar>
        }
        footer={
          <Pagination
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={setPage}
            onPageSizeChange={(n) => {
              setPageSize(n);
              setPage(0);
            }}
          />
        }
      />
    </div>
  );
}
