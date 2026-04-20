import { useQuery } from '@tanstack/react-query';
import api from '@/api/client';
import type { BarcodeFormat } from '@/lib/barcode';
import type { Setting } from '@/types';

export type LabelTemplate = 'avery_5160' | 'continuous_roll_2x1';

export interface LabelSettings {
  defaultFormat: BarcodeFormat;
  labelTemplate: LabelTemplate;
  includePrice: boolean;
}

const DEFAULTS: LabelSettings = {
  defaultFormat: 'code128',
  labelTemplate: 'avery_5160',
  includePrice: false,
};

function parseBool(value: string | undefined): boolean {
  return value === 'true' || value === '1';
}

function parseFormat(value: string | undefined): BarcodeFormat {
  return value === 'qr' || value === 'upc' ? value : 'code128';
}

function parseTemplate(value: string | undefined): LabelTemplate {
  return value === 'continuous_roll_2x1' ? 'continuous_roll_2x1' : 'avery_5160';
}

/**
 * Reads the three barcode-label settings from `/settings` and returns
 * typed defaults. Shares the same `['settings']` query key as
 * SettingsPage so edits propagate automatically.
 */
export function useLabelSettings(): LabelSettings {
  const { data: settings } = useQuery<Setting[]>({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings').then((r) => r.data),
  });

  if (!settings) return DEFAULTS;
  const map = new Map(settings.map((s) => [s.key, s.value]));
  return {
    defaultFormat: parseFormat(map.get('barcode_default_format')),
    labelTemplate: parseTemplate(map.get('barcode_label_template')),
    includePrice: parseBool(map.get('barcode_include_price')),
  };
}
