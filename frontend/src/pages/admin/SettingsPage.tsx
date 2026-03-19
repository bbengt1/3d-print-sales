import { useQuery } from '@tanstack/react-query';
import { Settings } from 'lucide-react';
import api from '@/api/client';
import type { Setting } from '@/types';

export default function SettingsPage() {
  const { data: settings, isLoading } = useQuery<Setting[]>({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings').then((r) => r.data),
  });

  const groups = {
    Business: ['currency'],
    Pricing: ['default_profit_margin_pct', 'platform_fee_pct', 'fixed_fee_per_order', 'sales_tax_pct'],
    Operations: ['electricity_cost_per_kwh', 'printer_power_draw_watts', 'failure_rate_pct'],
    Shipping: ['packaging_cost_per_order', 'shipping_charged_to_customer'],
  };

  const settingsMap = new Map(settings?.map((s) => [s.key, s]));

  const formatLabel = (key: string) =>
    key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div>
      <div className="flex items-center gap-3 mb-8">
        <Settings className="w-8 h-8 text-primary" />
        <h1 className="text-3xl font-bold">Admin Settings</h1>
      </div>

      {isLoading ? (
        <div className="space-y-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-6 h-32 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(groups).map(([group, keys]) => (
            <div key={group} className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4">{group}</h2>
              <div className="space-y-4">
                {keys.map((key) => {
                  const setting = settingsMap.get(key);
                  if (!setting) return null;
                  return (
                    <div key={key} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                      <div>
                        <p className="font-medium text-sm">{formatLabel(key)}</p>
                        {setting.notes && (
                          <p className="text-xs text-muted-foreground">{setting.notes}</p>
                        )}
                      </div>
                      <span className="font-mono text-sm bg-secondary px-3 py-1 rounded-md">
                        {setting.value}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
