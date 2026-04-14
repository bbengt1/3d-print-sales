import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import SettingsPage from '@/pages/admin/SettingsPage';
import api from '@/api/client';

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock('sonner', () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

const apiGet = api.get as unknown as Mock;
const apiPut = api.put as unknown as Mock;

const settingsResponse = [
  { key: 'currency', value: 'USD', notes: 'Currency code' },
  { key: 'default_profit_margin_pct', value: '40', notes: 'Target markup on total cost' },
  { key: 'platform_fee_pct', value: '9.5', notes: 'Etsy/Amazon/etc.' },
  { key: 'fixed_fee_per_order', value: '0.45', notes: 'Per-transaction fee' },
  { key: 'sales_tax_pct', value: '0', notes: 'Set if you collect tax' },
  { key: 'electricity_cost_per_kwh', value: '0.18', notes: 'Check your utility bill' },
  { key: 'printer_power_draw_watts', value: '120', notes: 'Average draw while printing' },
  { key: 'failure_rate_pct', value: '5', notes: 'Buffer for failed prints' },
  { key: 'packaging_cost_per_order', value: '1.25', notes: 'Boxes, tape, padding' },
  { key: 'shipping_charged_to_customer', value: '0', notes: '0 = free shipping model' },
  { key: 'ai_provider', value: 'chatgpt', notes: 'Selected insights provider: chatgpt, claude, or grok.' },
  { key: 'ai_chatgpt_model', value: 'gpt-4.1-mini', notes: 'OpenAI model used for read-only business insights.' },
  { key: 'ai_chatgpt_api_key', value: '', notes: 'OpenAI API key for ChatGPT insights.' },
  { key: 'ai_claude_model', value: 'claude-3-5-sonnet-latest', notes: 'Anthropic Claude model used for read-only business insights.' },
  { key: 'ai_claude_api_key', value: '', notes: 'Anthropic API key for Claude insights.' },
  { key: 'ai_grok_model', value: 'grok-3-mini', notes: 'xAI Grok model used for read-only business insights.' },
  { key: 'ai_grok_api_key', value: '', notes: 'xAI API key for Grok insights.' },
];

function renderSettingsPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>
  );
}

describe('SettingsPage', () => {
  beforeEach(() => {
    toastSuccess.mockReset();
    toastError.mockReset();
    apiGet.mockReset();
    apiPut.mockReset();
    apiGet.mockResolvedValue({ data: settingsResponse });
  });

  it('lets admins switch the active AI provider and save its model plus API key', async () => {
    const user = userEvent.setup();
    apiPut.mockResolvedValue({ data: [] });

    renderSettingsPage();

    await screen.findByText('AI Intelligence');
    await user.click(screen.getByRole('button', { name: /Claude/i }));

    const modelInput = screen.getByDisplayValue('claude-3-5-sonnet-latest');
    await user.clear(modelInput);
    await user.type(modelInput, 'claude-3-7-sonnet-latest');

    const apiKeyInput = screen.getByPlaceholderText('Paste API key');
    await user.type(apiKeyInput, 'claude-secret-key');

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(apiPut).toHaveBeenCalledWith('/settings/bulk', {
        settings: expect.objectContaining({
          ai_provider: 'claude',
          ai_claude_model: 'claude-3-7-sonnet-latest',
          ai_claude_api_key: 'claude-secret-key',
        }),
      });
    });

    expect(toastSuccess).toHaveBeenCalledWith('Settings saved');
  });
});
