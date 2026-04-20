import { Download } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';

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
    <div className="mb-6 flex flex-wrap items-end gap-3">
      <div className="space-y-1.5">
        <Label htmlFor="report-date-from" className="text-xs text-muted-foreground">
          From
        </Label>
        <Input
          id="report-date-from"
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFromChange(e.target.value)}
          className="w-auto"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="report-date-to" className="text-xs text-muted-foreground">
          To
        </Label>
        <Input
          id="report-date-to"
          type="date"
          value={dateTo}
          onChange={(e) => onDateToChange(e.target.value)}
          className="w-auto"
        />
      </div>
      {showPeriod && onPeriodChange ? (
        <div className="space-y-1.5">
          <Label htmlFor="report-period" className="text-xs text-muted-foreground">
            Period
          </Label>
          <select
            id="report-period"
            value={period}
            onChange={(e) => onPeriodChange(e.target.value)}
            className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
        </div>
      ) : null}
      {csvUrl ? (
        <Button variant="outline" onClick={handleExport}>
          <Download className="h-4 w-4" /> Export CSV
        </Button>
      ) : null}
    </div>
  );
}
