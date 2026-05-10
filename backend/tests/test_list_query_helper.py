from __future__ import annotations

import pytest
from sqlalchemy import select

from app.api.list_query import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ListQuery,
    apply_list_query,
)
from app.models.vendor import Vendor


def _vendor(name="X", is_active=True) -> Vendor:
    return Vendor(name=name, is_active=is_active)


def _stmt():
    return select(Vendor)


def test_default_page_size_constant():
    assert DEFAULT_PAGE_SIZE > 0
    assert MAX_PAGE_SIZE >= DEFAULT_PAGE_SIZE


def test_apply_list_query_no_params():
    lq = ListQuery()
    result = apply_list_query(
        _stmt(),
        Vendor,
        lq,
        allowed_sort=["name", "created_at"],
        search_columns=["name"],
        allowed_filters={"is_active": "is_active"},
    )
    assert result.page == 1
    assert result.page_size == DEFAULT_PAGE_SIZE
    assert result.offset == 0
    # Compiled SQL should contain LIMIT and OFFSET
    sql = str(result.stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "LIMIT" in sql.upper()


def test_apply_list_query_search_appends_where():
    lq = ListQuery(q="acme")
    result = apply_list_query(
        _stmt(),
        Vendor,
        lq,
        search_columns=["name"],
    )
    sql = str(result.stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "ilike" in sql or "like" in sql
    assert "%acme%" in sql


def test_apply_list_query_sort_descending():
    lq = ListQuery(sort="-name")
    result = apply_list_query(
        _stmt(),
        Vendor,
        lq,
        allowed_sort=["name"],
    )
    sql = str(result.stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "order by" in sql
    assert "desc" in sql


def test_apply_list_query_sort_disallowed_silently_dropped():
    lq = ListQuery(sort="password")
    result = apply_list_query(
        _stmt(),
        Vendor,
        lq,
        allowed_sort=["name"],
    )
    sql = str(result.stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    # Disallowed column should not appear in ORDER BY
    assert "password" not in sql or "order by" not in sql or "password" not in sql.split("order by", 1)[1]


def test_apply_list_query_in_filter():
    lq = ListQuery()
    result = apply_list_query(
        _stmt(),
        Vendor,
        lq,
        allowed_filters={"name": "name"},
        extra_filters={"name__in": "Acme,Globex,Initech"},
    )
    sql = str(result.stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "IN (" in sql.upper()


def test_apply_list_query_pagination_offset_math():
    lq = ListQuery(page=3, page_size=25)
    result = apply_list_query(
        _stmt(),
        Vendor,
        lq,
        allowed_sort=["name"],
    )
    assert result.offset == 50
    assert result.page == 3
    assert result.page_size == 25


def test_apply_list_query_unknown_filter_silently_dropped():
    """Filters not in allowed_filters never reach the SQL — defensive
    against accidental column exposure."""
    lq = ListQuery()
    result = apply_list_query(
        _stmt(),
        Vendor,
        lq,
        allowed_filters={"name": "name"},
        extra_filters={"hashed_password": "anything"},
    )
    sql = str(result.stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "hashed_password" not in sql.lower()


def test_apply_list_query_equality_filter():
    lq = ListQuery()
    result = apply_list_query(
        _stmt(),
        Vendor,
        lq,
        allowed_filters={"is_active": "is_active"},
        extra_filters={"is_active": True},
    )
    sql = str(result.stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "is_active" in sql


@pytest.mark.asyncio
async def test_executes_against_real_db(db_session):
    db_session.add(_vendor(name="Alpha", is_active=True))
    db_session.add(_vendor(name="Beta", is_active=False))
    db_session.add(_vendor(name="Acme Industries", is_active=True))
    await db_session.flush()

    lq = ListQuery(q="acme", sort="-name", page=1, page_size=10)
    result = apply_list_query(
        _stmt(),
        Vendor,
        lq,
        allowed_sort=["name"],
        search_columns=["name"],
    )
    rows = (await db_session.execute(result.stmt)).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "Acme Industries"


@pytest.mark.asyncio
async def test_pagination_against_real_db(db_session):
    for i in range(5):
        db_session.add(_vendor(name=f"V{i}"))
    await db_session.flush()
    lq = ListQuery(page=2, page_size=2, sort="name")
    result = apply_list_query(_stmt(), Vendor, lq, allowed_sort=["name"])
    rows = (await db_session.execute(result.stmt)).scalars().all()
    # Page 2 of size 2 with sort by name → V2, V3
    assert len(rows) == 2
    names = [r.name for r in rows]
    assert names == ["V2", "V3"]
