/**
 * Extract a safe, human-readable error message from an axios error.
 *
 * FastAPI returns:
 * - Business errors (`raise HTTPException(..., detail="Not enough stock")`)
 *   → `{ detail: "Not enough stock" }` (string)
 * - Pydantic validation errors (422)
 *   → `{ detail: [{ type, loc, msg, input }, ...] }` (array)
 *
 * Passing the array straight into a `toast.error(...)` (or any React
 * child) triggers React error #31 ("Objects are not valid as a React
 * child"). This helper handles both shapes uniformly.
 *
 * @param err - the caught error (usually from axios)
 * @param fallback - message to show if no usable detail is found
 */
export function getApiErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  const detail = extractDetail(err);

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map(formatValidationItem).filter(Boolean).join(' · ') || fallback;
  }

  // axios-level message (e.g. "Network Error")
  if (err && typeof err === 'object' && 'message' in err) {
    const m = (err as { message?: unknown }).message;
    if (typeof m === 'string' && m.trim()) return m;
  }

  return fallback;
}

function extractDetail(err: unknown): unknown {
  if (!err || typeof err !== 'object') return undefined;
  const response = (err as { response?: { data?: unknown } }).response;
  if (!response || typeof response !== 'object') return undefined;
  const data = (response as { data?: unknown }).data;
  if (!data || typeof data !== 'object') return undefined;
  return (data as { detail?: unknown }).detail;
}

interface PydanticValidationItem {
  type?: string;
  loc?: Array<string | number>;
  msg?: string;
  input?: unknown;
}

function formatValidationItem(raw: unknown): string {
  if (typeof raw === 'string') return raw;
  if (!raw || typeof raw !== 'object') return '';
  const item = raw as PydanticValidationItem;
  const field = formatLoc(item.loc);
  const msg = item.msg || item.type || '';
  if (!msg) return field || '';
  return field ? `${field}: ${msg}` : msg;
}

function formatLoc(loc: Array<string | number> | undefined): string {
  if (!Array.isArray(loc) || loc.length === 0) return '';
  // Drop the first "body" / "query" / "path" root marker when present.
  const parts = loc[0] === 'body' || loc[0] === 'query' || loc[0] === 'path' ? loc.slice(1) : loc;
  return parts.map(String).join('.');
}
