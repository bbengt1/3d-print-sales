const MODULE_LOAD_RECOVERY_KEY = '3d-print-sales:module-load-recovery';

const MODULE_LOAD_ERROR_PATTERNS = [
  /failed to fetch dynamically imported module/i,
  /importing a module script failed/i,
  /error loading dynamically imported module/i,
  /loading chunk \d+ failed/i,
  /chunkloaderror/i,
];

export function isModuleLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;

  const details = [error.name, error.message].filter(Boolean).join(' ');
  return MODULE_LOAD_ERROR_PATTERNS.some((pattern) => pattern.test(details));
}

export function recoverFromModuleLoadError(error: unknown): boolean {
  if (!isModuleLoadError(error)) return false;
  if (typeof window === 'undefined') return false;

  const reloadMarker = `${__APP_BUILD_ID__}:${window.location.pathname}`;

  try {
    if (window.sessionStorage.getItem(MODULE_LOAD_RECOVERY_KEY) === reloadMarker) {
      return false;
    }

    window.sessionStorage.setItem(MODULE_LOAD_RECOVERY_KEY, reloadMarker);
  } catch {
    return false;
  }

  window.location.reload();
  return true;
}
