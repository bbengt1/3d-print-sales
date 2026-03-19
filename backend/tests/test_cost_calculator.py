from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio

from app.services.cost_calculator import CostCalculator


@pytest.mark.asyncio
async def test_calculate_basic(db_session, seed_settings, seed_rates, seed_material):
    calc = CostCalculator(db_session)
    result = await calc.calculate(
        material_id=seed_material.id,
        qty_per_plate=1,
        num_plates=1,
        material_per_plate_g=Decimal("45"),
        print_time_per_plate_hrs=Decimal("2.5"),
        labor_mins=Decimal("15"),
        design_time_hrs=Decimal("0.5"),
        shipping_cost=Decimal("0"),
        target_margin_pct=Decimal("40"),
    )

    assert "total_cost" in result
    assert "net_profit" in result
    assert "price_per_piece" in result
    assert result["total_cost"] > 0
    assert result["price_per_piece"] > result["cost_per_piece"]
    assert result["net_profit"] > 0


@pytest.mark.asyncio
async def test_calculate_multi_plate(db_session, seed_settings, seed_rates, seed_material):
    calc = CostCalculator(db_session)
    result = await calc.calculate(
        material_id=seed_material.id,
        qty_per_plate=4,
        num_plates=3,
        material_per_plate_g=Decimal("80"),
        print_time_per_plate_hrs=Decimal("4"),
        labor_mins=Decimal("20"),
        design_time_hrs=Decimal("1"),
        shipping_cost=Decimal("0"),
        target_margin_pct=Decimal("40"),
    )

    # Multi-plate should have higher material cost than single plate
    assert result["material_cost"] > Decimal("5")
    assert result["machine_cost"] > Decimal("10")


@pytest.mark.asyncio
async def test_calculate_zero_design_time(db_session, seed_settings, seed_rates, seed_material):
    calc = CostCalculator(db_session)
    result = await calc.calculate(
        material_id=seed_material.id,
        qty_per_plate=1,
        num_plates=1,
        material_per_plate_g=Decimal("45"),
        print_time_per_plate_hrs=Decimal("2.5"),
        labor_mins=Decimal("10"),
        design_time_hrs=Decimal("0"),
        shipping_cost=Decimal("0"),
        target_margin_pct=Decimal("40"),
    )

    assert result["design_cost"] == Decimal("0")
    assert result["total_cost"] > 0


@pytest.mark.asyncio
async def test_calculate_with_shipping(db_session, seed_settings, seed_rates, seed_material):
    calc = CostCalculator(db_session)
    result_no_ship = await calc.calculate(
        material_id=seed_material.id,
        qty_per_plate=1,
        num_plates=1,
        material_per_plate_g=Decimal("45"),
        print_time_per_plate_hrs=Decimal("2.5"),
        labor_mins=Decimal("10"),
        design_time_hrs=Decimal("0"),
        shipping_cost=Decimal("0"),
        target_margin_pct=Decimal("40"),
    )
    result_with_ship = await calc.calculate(
        material_id=seed_material.id,
        qty_per_plate=1,
        num_plates=1,
        material_per_plate_g=Decimal("45"),
        print_time_per_plate_hrs=Decimal("2.5"),
        labor_mins=Decimal("10"),
        design_time_hrs=Decimal("0"),
        shipping_cost=Decimal("5.00"),
        target_margin_pct=Decimal("40"),
    )

    assert result_with_ship["total_cost"] > result_no_ship["total_cost"]
    assert result_with_ship["shipping_cost"] == Decimal("5.00")


@pytest.mark.asyncio
async def test_calculate_invalid_material(db_session, seed_settings, seed_rates):
    import uuid
    from fastapi import HTTPException

    calc = CostCalculator(db_session)
    with pytest.raises(HTTPException) as exc_info:
        await calc.calculate(
            material_id=uuid.uuid4(),
            qty_per_plate=1,
            num_plates=1,
            material_per_plate_g=Decimal("45"),
            print_time_per_plate_hrs=Decimal("2.5"),
            labor_mins=Decimal("10"),
            design_time_hrs=Decimal("0"),
            shipping_cost=Decimal("0"),
            target_margin_pct=Decimal("40"),
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_calculate_margin_consistency(db_session, seed_settings, seed_rates, seed_material):
    """Revenue minus costs minus fees should equal net profit."""
    calc = CostCalculator(db_session)
    result = await calc.calculate(
        material_id=seed_material.id,
        qty_per_plate=8,
        num_plates=1,
        material_per_plate_g=Decimal("60"),
        print_time_per_plate_hrs=Decimal("3"),
        labor_mins=Decimal("10"),
        design_time_hrs=Decimal("0"),
        shipping_cost=Decimal("0"),
        target_margin_pct=Decimal("40"),
    )

    expected_profit = result["total_revenue"] - result["total_cost"] - result["platform_fees"]
    assert abs(result["net_profit"] - expected_profit) < Decimal("0.01")
