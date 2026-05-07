import { afterEach, describe, expect, it, vi } from 'vitest';
import { openBlankPrintWindow, printWindowWhenReady, PrintWindowBlockedError, writePrintWindow } from './printWindow';

function createPrintWindow() {
  const state = { html: '' };
  const printWindow = {
    opener: {},
    document: {
      readyState: 'complete',
      images: [],
      open: vi.fn(),
      write: vi.fn((html: string) => {
        state.html = html;
      }),
      close: vi.fn(),
    },
    addEventListener: vi.fn(),
    focus: vi.fn(),
    print: vi.fn(),
    requestAnimationFrame: vi.fn((cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    }),
    setTimeout: vi.fn((cb: () => void) => {
      cb();
      return 1;
    }),
  } as unknown as Window;

  return { printWindow, state };
}

describe('printWindow', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('opens a writable popup without noopener features and writes a preparing state', () => {
    const { printWindow, state } = createPrintWindow();
    const open = vi.spyOn(window, 'open').mockReturnValue(printWindow);

    const win = openBlankPrintWindow('Preparing labels');

    expect(win).toBe(printWindow);
    expect(open).toHaveBeenCalledWith('', '_blank', 'width=800,height=900');
    expect(printWindow.document.open).toHaveBeenCalled();
    expect(printWindow.document.close).toHaveBeenCalled();
    expect(state.html).toContain('Preparing labels...');
  });

  it('throws a clear error when the popup is blocked', () => {
    vi.spyOn(window, 'open').mockReturnValue(null);

    expect(() => openBlankPrintWindow()).toThrow(PrintWindowBlockedError);
  });

  it('writes final label HTML and schedules print after the document is ready', () => {
    const { printWindow, state } = createPrintWindow();

    writePrintWindow(printWindow, 'Label', '<div class="label">Test</div>');

    expect(state.html).toContain('<div class="label">Test</div>');
    expect(state.html).toContain('printWhenReady');
    expect(printWindow.focus).toHaveBeenCalled();
  });

  it('prints an existing raw document after loaded images settle', async () => {
    const { printWindow } = createPrintWindow();

    printWindowWhenReady(printWindow);
    await Promise.resolve();

    expect(printWindow.print).toHaveBeenCalled();
  });
});
