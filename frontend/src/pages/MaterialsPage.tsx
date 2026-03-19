import { useQuery } from '@tanstack/react-query';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import type { Material } from '@/types';

export default function MaterialsPage() {
  const { data: materials, isLoading } = useQuery<Material[]>({
    queryKey: ['materials'],
    queryFn: () => api.get('/materials').then((r) => r.data),
  });

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Materials</h1>
      {isLoading ? (
        <div className="bg-card border border-border rounded-lg p-4 h-48 animate-pulse" />
      ) : (
        <div className="overflow-x-auto bg-card border border-border rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Brand</th>
                <th className="px-4 py-3 font-medium text-right">Spool (g)</th>
                <th className="px-4 py-3 font-medium text-right">Price</th>
                <th className="px-4 py-3 font-medium text-right">Usable (g)</th>
                <th className="px-4 py-3 font-medium text-right">Cost/g</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {materials?.map((m) => (
                <tr key={m.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{m.name}</td>
                  <td className="px-4 py-3">{m.brand}</td>
                  <td className="px-4 py-3 text-right">{m.spool_weight_g}</td>
                  <td className="px-4 py-3 text-right">{formatCurrency(m.spool_price)}</td>
                  <td className="px-4 py-3 text-right">{m.net_usable_g}</td>
                  <td className="px-4 py-3 text-right">${Number(m.cost_per_g).toFixed(4)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${m.active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'}`}>
                      {m.active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
