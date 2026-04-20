import { Tooltip } from 'recharts';
import type { ComponentProps } from 'react';

/**
 * Shared content style for recharts tooltips. Business-app neutral: card
 * background, border token, soft corner, compact typography. Re-use via
 * the `<ChartTooltip>` wrapper or spread into `contentStyle={...}` when a
 * chart needs additional overrides recharts doesn't pass through.
 */
export const chartTooltipContentStyle = {
  backgroundColor: 'var(--color-card)',
  border: '1px solid var(--color-border)',
  borderRadius: '8px',
  fontSize: '12px',
  color: 'var(--color-foreground)',
} as const;

type ChartTooltipProps = ComponentProps<typeof Tooltip>;

/**
 * Consistent recharts tooltip. Pass the same formatter / labelFormatter you
 * would pass to recharts' built-in `<Tooltip>`; the content style is applied
 * automatically so every chart in the app matches.
 */
export function ChartTooltip(props: ChartTooltipProps) {
  return <Tooltip contentStyle={chartTooltipContentStyle} {...props} />;
}

/**
 * Palette derived from the trust-blue primary. Use for categorical series
 * (pie slices, multi-series bars) so charts never drift off-brand. Ordered
 * for legibility when the first N colors are used.
 */
export const chartCategoricalPalette = [
  '#2563eb', // primary trust-blue
  '#0ea5e9', // sky-500
  '#14b8a6', // teal-500
  '#64748b', // slate-500
  '#94a3b8', // slate-400
  '#475569', // slate-600
] as const;
