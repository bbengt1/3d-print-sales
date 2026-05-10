"""Shared list-query helper for endpoint consistency (#264).

Endpoints accept a uniform set of query parameters:

  - `q`             — free-text search (interpretation is per-endpoint)
  - `sort`          — comma-separated columns, `-` prefix for desc
                      (e.g. `sort=name,-created_at`)
  - `page`          — 1-indexed page number
  - `page_size`     — capped at MAX_PAGE_SIZE
  - `?{field}=v`    — equality filter on `field`
  - `?{field}__in=a,b` — membership filter

This module exposes `ListQuery` (Pydantic dependency-injection model)
and `apply_list_query(stmt, model, qs, *, allowed_sort, allowed_filters,
search_columns)` to compose the request into a SQLAlchemy `select`.

Adopted incrementally — existing endpoints keep their bespoke shape
until they're refactored. New endpoints should use this helper.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query
from sqlalchemy import Select, and_, or_


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass
class ListQuery:
    """FastAPI dependency-style holder for the shared query parameters.

    Construct with FastAPI's `Depends` machinery — see `list_query_dep`.
    """

    q: str | None = None
    sort: str | None = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


def list_query_dep(
    q: str | None = Query(None, description="Free-text search"),
    sort: str | None = Query(None, description="Comma-separated columns, prefix `-` for desc"),
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description=f"Page size (max {MAX_PAGE_SIZE})"),
) -> ListQuery:
    return ListQuery(q=q, sort=sort, page=page, page_size=page_size)


@dataclass
class ListQueryResult:
    stmt: Select
    page: int
    page_size: int
    offset: int


def apply_list_query(
    stmt: Select,
    model: type,
    lq: ListQuery,
    *,
    allowed_sort: list[str] | None = None,
    search_columns: list[str] | None = None,
    allowed_filters: dict[str, str] | None = None,
    extra_filters: dict[str, object] | None = None,
) -> ListQueryResult:
    """Compose a `select` statement with sort + search + pagination.

    Args:
        stmt: starting `select(model)` (caller may have already added joins / where)
        model: the SQLAlchemy model class
        lq: parsed `ListQuery`
        allowed_sort: list of column names callers may sort by; missing entries
            are silently skipped (so a malicious sort param can't access
            arbitrary columns)
        search_columns: column names that `q=` filters across with ILIKE
        allowed_filters: `{query_param_name: model_attr}` for equality + __in
            filters. Use the same name on both sides if they match
        extra_filters: dict of extra `query_param_name → value-from-request`
            collected by the caller (FastAPI doesn't let us read arbitrary
            query params inside the helper). Passed verbatim through the
            `allowed_filters` logic.

    Returns: a `ListQueryResult` with the composed stmt + pagination metadata.
    The caller still runs `await db.execute(result.stmt)` to fetch rows and
    runs a parallel `count(*)` query if total-count is needed.
    """
    allowed_sort = allowed_sort or []
    search_columns = search_columns or []
    allowed_filters = allowed_filters or {}
    extra_filters = extra_filters or {}

    # Search
    if lq.q and search_columns:
        like = f"%{lq.q}%"
        clauses = []
        for col_name in search_columns:
            col = getattr(model, col_name, None)
            if col is not None:
                clauses.append(col.ilike(like))
        if clauses:
            stmt = stmt.where(or_(*clauses))

    # Filters from `extra_filters` dict
    for param_name, value in extra_filters.items():
        if value is None:
            continue
        if param_name.endswith("__in"):
            base = param_name[: -len("__in")]
            attr = allowed_filters.get(base)
            if attr is None:
                continue
            col = getattr(model, attr, None)
            if col is None:
                continue
            values = [v.strip() for v in str(value).split(",") if v.strip()]
            if values:
                stmt = stmt.where(col.in_(values))
        else:
            attr = allowed_filters.get(param_name)
            if attr is None:
                continue
            col = getattr(model, attr, None)
            if col is None:
                continue
            stmt = stmt.where(col == value)

    # Sort
    if lq.sort:
        order_clauses = []
        for token in lq.sort.split(","):
            token = token.strip()
            if not token:
                continue
            desc = token.startswith("-")
            col_name = token[1:] if desc else token
            if col_name not in allowed_sort:
                continue
            col = getattr(model, col_name, None)
            if col is None:
                continue
            order_clauses.append(col.desc() if desc else col.asc())
        if order_clauses:
            stmt = stmt.order_by(*order_clauses)

    # Pagination
    offset = (lq.page - 1) * lq.page_size
    stmt = stmt.offset(offset).limit(lq.page_size)
    return ListQueryResult(stmt=stmt, page=lq.page, page_size=lq.page_size, offset=offset)
