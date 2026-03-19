import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Plus } from 'lucide-react';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import type { Job } from '@/types';

export default function JobsPage() {
  const { data: jobs, isLoading } = useQuery<Job[]>({
    queryKey: ['jobs'],
    queryFn: () => api.get('/jobs').then((r) => r.data),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Jobs</h1>
        <Link
          to="/jobs/new"
          className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity no-underline"
        >
          <Plus className="w-4 h-4" /> New Job
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-4 h-16 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto bg-card border border-border rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">Job #</th>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Customer</th>
                <th className="px-4 py-3 font-medium">Product</th>
                <th className="px-4 py-3 font-medium text-right">Pieces</th>
                <th className="px-4 py-3 font-medium text-right">Revenue</th>
                <th className="px-4 py-3 font-medium text-right">Profit</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {jobs?.map((job) => (
                <tr key={job.id} className="border-b border-border last:border-0 hover:bg-accent/50 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/jobs/${job.id}`} className="text-primary hover:underline font-medium no-underline">
                      {job.job_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{job.date}</td>
                  <td className="px-4 py-3">{job.customer_name || '—'}</td>
                  <td className="px-4 py-3">{job.product_name}</td>
                  <td className="px-4 py-3 text-right">{job.total_pieces}</td>
                  <td className="px-4 py-3 text-right">{formatCurrency(job.total_revenue)}</td>
                  <td className="px-4 py-3 text-right">{formatCurrency(job.net_profit)}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                      {job.status}
                    </span>
                  </td>
                </tr>
              ))}
              {jobs?.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                    No jobs yet. Create your first job to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
