import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, KeyRound, Settings, Save } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { getApiErrorMessage } from '@/lib/apiError';
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

const aiProviders = [
  { value: 'chatgpt', label: 'ChatGPT', modelKey: 'ai_chatgpt_model', apiKey: 'ai_chatgpt_api_key' },
  { value: 'claude', label: 'Claude', modelKey: 'ai_claude_model', apiKey: 'ai_claude_api_key' },
  { value: 'grok', label: 'Grok', modelKey: 'ai_grok_model', apiKey: 'ai_grok_api_key' },
] as const;

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
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to save settings'));
    } finally {
      setSaving(false);
    }
  };

  const settingsMap = new Map(settings?.map((s) => [s.key, s]));
  const activeProvider = values.ai_provider || 'chatgpt';
  const activeProviderConfig = aiProviders.find((provider) => provider.value === activeProvider) || aiProviders[0];

  const renderSettingInput = (key: string, helperLabel?: string) => {
    const setting = settingsMap.get(key);
    if (!setting) return null;
    const isSecret = key.endsWith('_api_key');
    return (
      <div key={key} className="space-y-2">
        <div>
          <p className="font-medium text-sm">{helperLabel || formatLabel(key)}</p>
          {setting.notes && (
            <p className="text-xs text-muted-foreground">{setting.notes}</p>
          )}
        </div>
        <input
          type={isSecret ? 'password' : 'text'}
          value={values[key] ?? ''}
          onChange={(e) => update(key, e.target.value)}
          placeholder={isSecret ? 'Paste API key' : undefined}
          className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring font-mono text-sm"
        />
      </div>
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Settings className="w-8 h-8 text-primary" />
          <div>
            <h1 className="text-2xl font-semibold">Settings</h1>
            <p className="text-sm text-muted-foreground">Configure business parameters</p>
          </div>
        </div>
        {dirty && (
          <Button onClick={saveAll} disabled={saving}>
            <Save className="h-4 w-4" />
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} rows={2} />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="bg-card border border-border rounded-lg p-6">
            <div className="mb-5 flex items-start gap-3">
              <div className="rounded-md bg-primary/10 p-3 text-primary">
                <Bot className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-base font-semibold">AI Intelligence</h2>
                <p className="text-sm text-muted-foreground">
                  Configure one supported provider for the read-only Insights workspace. Keep the choice obvious, the model explicit, and the secrets scoped to admins only.
                </p>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              {aiProviders.map((provider) => {
                const isActive = activeProvider === provider.value;
                return (
                  <button
                    key={provider.value}
                    type="button"
                    onClick={() => update('ai_provider', provider.value)}
                    className={`rounded-md border p-4 text-left transition-colors ${
                      isActive
                        ? 'border-primary bg-primary/5'
                        : 'border-border bg-background hover:border-primary/30'
                    }`}
                  >
                    <p className="font-semibold">{provider.label}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {values[provider.modelKey] || 'No model configured'}
                    </p>
                  </button>
                );
              })}
            </div>

            <div className="mt-6 rounded-md border border-border bg-background p-5">
              <div className="mb-4 flex items-start gap-3">
                <div className="rounded-md bg-primary/10 p-2 text-primary">
                  <KeyRound className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-semibold">{aiProviders.find((provider) => provider.value === activeProviderConfig.value)?.label} configuration</h3>
                  <p className="text-sm text-muted-foreground">
                    Progressive disclosure for Hick&apos;s Law: edit the active provider here, switch providers when you want to configure a different one.
                  </p>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {renderSettingInput(activeProviderConfig.modelKey, 'Model')}
                {renderSettingInput(activeProviderConfig.apiKey, 'API Key')}
              </div>
            </div>
          </div>

          {Object.entries(groups).map(([group, { keys, description }]) => (
            <div key={group} className="bg-card border border-border rounded-lg p-6">
              <div className="mb-4">
                <h2 className="text-base font-semibold">{group}</h2>
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
