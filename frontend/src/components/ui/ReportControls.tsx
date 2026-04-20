import { Download } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface ReportControlsProps {
  dateFrom: string;
  dateTo: string;
  period?: string;
  showPeriod?: boolean;
  csvUrl?: string;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
  onPeriodChange?: (v: string) => void;
}

export default function ReportControls({
  dateFrom,
  dateTo,
  period,
  showPeriod = true,
  csvUrl,
  onDateFromChange,
  onDateToChange,
  onPeriodChange,
}: ReportControlsProps) {
  const inputCls = 'px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring text-sm';

  const handleExport = () => {
    if (!csvUrl) return;
    const params = new URLSearchParams();
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (period) params.set('period', period);
    const url = `/api/v1${csvUrl}${params.toString() ? '?' + params.toString() : ''}`;
    window.open(url, '_blank');
  };

  return (
    <div className="flex flex-wrap gap-3 mb-6 items-end">
      <div>
        <label className="block text-xs text-muted-foreground mb-1">From</label>
        <input type="date" value={dateFrom} onChange={(e) => onDateFromChange(e.target.value)} className={inputCls} />
      </div>
      <div>
        <label className="block text-xs text-muted-foreground mb-1">To</label>
        <input type="date" value={dateTo} onChange={(e) => onDateToChange(e.target.value)} className={inputCls} />
      </div>
      {showPeriod && onPeriodChange && (
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Period</label>
          <select value={period} onChange={(e) => onPeriodChange(e.target.value)} className={inputCls}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
        </div>
      )}
      {csvUrl && (
        <Button variant="outline" onClick={handleExport}>
          <Download className="h-4 w-4" /> Export CSV
        </Button>
      )}
    </div>
  );
}
