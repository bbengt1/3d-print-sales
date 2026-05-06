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
 * Color-blind friendly categorical palette for report charts. Pair series
 * with legends/labels; hue alone should never carry the meaning.
 */
export const chartCategoricalPalette = [
  '#005ea8', // operational blue
  '#7a4a00', // brown-amber
  '#006b5b', // blue-green
  '#b42318', // vermillion red
  '#5b677a', // slate
  '#6d3f8f', // purple
] as const;
