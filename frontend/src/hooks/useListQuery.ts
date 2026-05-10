import { useMemo, useState } from 'react';
import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import api from '@/api/client';

interface UseListQueryOptions {
  resource: string;
  initialLimit?: number;
  initialSearch?: string;
  initialFilters?: Record<string, string | number | undefined>;
  staleTime?: number;
  enabled?: boolean;
}

export interface ListQueryState<T> {
  data: T[];
  total: number;
  isLoading: boolean;
  isError: boolean;
  search: string;
  setSearch: (s: string) => void;
  page: number;
  setPage: (p: number) => void;
  limit: number;
  setLimit: (n: number) => void;
  filters: Record<string, string | number | undefined>;
  setFilter: (key: string, value: string | number | undefined) => void;
  refetch: () => void;
  raw: UseQueryResult<{ items: T[]; total: number; skip: number; limit: number } | T[]>;
}

/**
 * Generic list-query hook. Backend list endpoints either return
 * `{items, total, skip, limit}` (paginated) or a bare array. Handles both.
 */
export function useListQuery<T>(opts: UseListQueryOptions): ListQueryState<T> {
  const { resource, initialLimit = 50, initialSearch = '', initialFilters = {}, staleTime, enabled = true } = opts;
  const [search, setSearch] = useState(initialSearch);
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(initialLimit);
  const [filters, setFilters] = useState<Record<string, string | number | undefined>>(initialFilters);

  const setFilter = (key: string, value: string | number | undefined) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(0);
  };

  const queryKey = useMemo(() => [resource, search, page, limit, filters], [resource, search, page, limit, filters]);

  const raw = useQuery({
    queryKey,
    enabled,
    staleTime,
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      params.set('skip', String(page * limit));
      params.set('limit', String(limit));
      for (const [k, v] of Object.entries(filters)) {
        if (v !== undefined && v !== '' && v !== null) params.set(k, String(v));
      }
      const r = await api.get(`/${resource}?${params.toString()}`);
      return r.data;
    },
  });

  const items: T[] = Array.isArray(raw.data) ? raw.data : raw.data?.items ?? [];
  const total: number = Array.isArray(raw.data) ? raw.data.length : raw.data?.total ?? 0;

  return {
    data: items,
    total,
    isLoading: raw.isLoading,
    isError: raw.isError,
    search,
    setSearch,
    page,
    setPage,
    limit,
    setLimit,
    filters,
    setFilter,
    refetch: () => raw.refetch(),
    raw,
  };
}
