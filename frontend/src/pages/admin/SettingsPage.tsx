import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Settings, Save } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import type { Setting } from '@/types';

const groups: Record<string, { keys: string[]; description: string }> = {
  Business: {
    keys: ['currency'],
    description: 'General business configuration',
  },
  Pricing: {
    keys: ['default_profit_margin_pct', 'platform_fee_pct', 'fixed_fee_per_order', 'sales_tax_pct'],
    description: 'Profit margins, platform fees, and tax settings',
  },
  Operations: {
    keys: ['electricity_cost_per_kwh', 'printer_power_draw_watts', 'failure_rate_pct'],
    description: 'Printer and electricity cost configuration',
  },
  Shipping: {
    keys: ['packaging_cost_per_order', 'shipping_charged_to_customer'],
    description: 'Packaging and shipping cost settings',
  },
};

const formatLabel = (key: string) =>
  key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery<Setting[]>({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings').then((r) => r.data),
  });

  const [values, setValues] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings) {
      const map: Record<string, string> = {};
      settings.forEach((s) => { map[s.key] = s.value; });
      setValues(map);
      setDirty(false);
    }
  }, [settings]);

  const update = (key: string, value: string) => {
    setValues((v) => ({ ...v, [key]: value }));
    setDirty(true);
  };

  const saveAll = async () => {
    setSaving(true);
    try {
      await api.put('/settings/bulk', { settings: values });
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      toast.success('Settings saved');
      setDirty(false);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const settingsMap = new Map(settings?.map((s) => [s.key, s]));

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Settings className="w-8 h-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Settings</h1>
            <p className="text-sm text-muted-foreground">Configure business parameters</p>
          </div>
        </div>
        {dirty && (
          <button
            onClick={saveAll}
            disabled={saving}
            className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-6 h-32 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groups).map(([group, { keys, description }]) => (
            <div key={group} className="bg-card border border-border rounded-lg p-6">
              <div className="mb-4">
                <h2 className="text-lg font-semibold">{group}</h2>
                <p className="text-sm text-muted-foreground">{description}</p>
              </div>
              <div className="space-y-4">
                {keys.map((key) => {
                  const setting = settingsMap.get(key);
                  if (!setting) return null;
                  return (
                    <div key={key} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 py-2 border-b border-border last:border-0">
                      <div className="sm:w-1/2">
                        <p className="font-medium text-sm">{formatLabel(key)}</p>
                        {setting.notes && (
                          <p className="text-xs text-muted-foreground">{setting.notes}</p>
                        )}
                      </div>
                      <div className="sm:w-1/2">
                        <input
                          type="text"
                          value={values[key] ?? ''}
                          onChange={(e) => update(key, e.target.value)}
                          className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring font-mono text-sm"
                        />
                      </div>
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
