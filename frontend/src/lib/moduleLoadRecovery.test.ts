import { beforeEach, describe, expect, it, vi } from 'vitest';
import { isModuleLoadError, recoverFromModuleLoadError } from './moduleLoadRecovery';

describe('moduleLoadRecovery', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        pathname: '/control-center',
        reload: vi.fn(),
      },
    });
  });

  it('identifies browser dynamic import failures', () => {
    expect(isModuleLoadError(new Error('Importing a module script failed.'))).toBe(true);
    expect(isModuleLoadError(new Error('Failed to fetch dynamically imported module'))).toBe(true);
    expect(isModuleLoadError(new Error('regular render failure'))).toBe(false);
  });

  it('reloads only once per build and route', () => {
    const error = new Error('Importing a module script failed.');

    expect(recoverFromModuleLoadError(error)).toBe(true);
    expect(window.location.reload).toHaveBeenCalledTimes(1);

    expect(recoverFromModuleLoadError(error)).toBe(false);
    expect(window.location.reload).toHaveBeenCalledTimes(1);
  });
});
