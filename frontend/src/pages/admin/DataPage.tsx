import { useState } from 'react';
import { Download, FileSpreadsheet } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';

export default function DataPage() {
  const [exporting, setExporting] = useState<string | null>(null);

  const exportCsv = async (resource: string, label: string) => {
    setExporting(resource);
    try {
      const { data } = await api.get(`/${resource}`);
      const items = Array.isArray(data) ? data : data.items || [];
      if (items.length === 0) {
        toast.error(`No ${label.toLowerCase()} to export`);
        return;
      }
      const headers = Object.keys(items[0]);
      const csv = [
        headers.join(','),
        ...items.map((row: Record<string, any>) =>
          headers.map((h) => {
            const val = row[h];
            if (val === null || val === undefined) return '';
            const str = String(val);
            return str.includes(',') || str.includes('"') || str.includes('\n')
              ? `"${str.replace(/"/g, '""')}"`
              : str;
          }).join(',')
        ),
      ].join('\n');

      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${resource}-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${label} exported`);
    } catch {
      toast.error(`Failed to export ${label.toLowerCase()}`);
    } finally {
      setExporting(null);
    }
  };

  const exports = [
    { resource: 'jobs', label: 'Jobs', description: 'All jobs with cost breakdowns, pricing, and profit analysis' },
    { resource: 'materials', label: 'Materials', description: 'Filament materials with pricing and usage data' },
    { resource: 'rates', label: 'Rates', description: 'Labor, machine, and overhead rates' },
    { resource: 'customers', label: 'Customers', description: 'Customer records with job counts' },
    { resource: 'settings', label: 'Settings', description: 'All business configuration values' },
  ];

  return (
    <div>
      <div className="flex items-center gap-3 mb-8">
        <Download className="w-8 h-8 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">Data Export</h1>
          <p className="text-sm text-muted-foreground">Export your data as CSV files</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {exports.map(({ resource, label, description }) => (
          <div key={resource} className="bg-card border border-border rounded-lg p-6 flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <FileSpreadsheet className="w-5 h-5 text-muted-foreground mt-0.5" />
              <div>
                <h3 className="font-semibold">{label}</h3>
                <p className="text-sm text-muted-foreground mt-1">{description}</p>
              </div>
            </div>
            <button
              onClick={() => exportCsv(resource, label)}
              disabled={exporting === resource}
              className="shrink-0 inline-flex items-center gap-2 px-3 py-2 border border-border rounded-lg text-sm font-medium hover:bg-accent transition-colors disabled:opacity-50 cursor-pointer"
            >
              <Download className="w-4 h-4" />
              {exporting === resource ? 'Exporting...' : 'Export'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
