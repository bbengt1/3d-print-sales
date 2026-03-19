from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.rate import Rate
from app.models.setting import Setting


class CostCalculator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_setting(self, key: str) -> Decimal:
        result = await self.db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        return Decimal(setting.value) if setting else Decimal(0)

    async def _get_rate(self, name: str) -> Decimal:
        result = await self.db.execute(
            select(Rate).where(Rate.name == name, Rate.active == True)
        )
        rate = result.scalar_one_or_none()
        return rate.value if rate else Decimal(0)

    async def calculate(
        self,
        material_id: uuid.UUID,
        qty_per_plate: int,
        num_plates: int,
        material_per_plate_g: Decimal,
        print_time_per_plate_hrs: Decimal,
        labor_mins: Decimal,
        design_time_hrs: Decimal,
        shipping_cost: Decimal,
        target_margin_pct: Decimal,
    ) -> dict:
        # Validate material exists
        result = await self.db.execute(select(Material).where(Material.id == material_id))
        material = result.scalar_one_or_none()
        if not material:
            raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found")
        if not material.active:
            raise HTTPException(status_code=400, detail=f"Material '{material.name}' is inactive")
        cost_per_g = material.cost_per_g

        # Fetch settings
        electricity_rate = await self._get_setting("electricity_cost_per_kwh")
        printer_watts = await self._get_setting("printer_power_draw_watts")
        failure_rate_pct = await self._get_setting("failure_rate_pct")
        packaging = await self._get_setting("packaging_cost_per_order")
        platform_fee_pct = await self._get_setting("platform_fee_pct")
        fixed_fee = await self._get_setting("fixed_fee_per_order")

        # Fetch rates
        labor_rate = await self._get_rate("Labor rate")
        machine_rate = await self._get_rate("Machine rate")
        overhead_pct = await self._get_rate("Overhead %")

        total_pieces = qty_per_plate * num_plates
        if total_pieces <= 0:
            raise HTTPException(status_code=400, detail="Total pieces must be greater than 0")

        total_print_hrs = print_time_per_plate_hrs * num_plates

        # Cost calculations
        electricity_cost = (printer_watts / Decimal(1000)) * total_print_hrs * electricity_rate
        material_cost = material_per_plate_g * num_plates * cost_per_g
        labor_cost = (labor_mins / Decimal(60)) * labor_rate
        design_cost = design_time_hrs * labor_rate
        machine_cost = total_print_hrs * machine_rate
        packaging_cost = packaging

        subtotal = (
            electricity_cost + material_cost + labor_cost + design_cost
            + machine_cost + packaging_cost + shipping_cost
        )

        failure_buffer = subtotal * (failure_rate_pct / Decimal(100))
        subtotal_with_buffer = subtotal + failure_buffer

        overhead = subtotal_with_buffer * (overhead_pct / Decimal(100))
        total_cost = subtotal_with_buffer + overhead

        cost_per_piece = total_cost / total_pieces

        # Pricing
        margin_divisor = Decimal(1) - target_margin_pct / Decimal(100)
        if margin_divisor <= 0:
            raise HTTPException(status_code=400, detail="Target margin must be less than 100%")
        price_per_piece = cost_per_piece / margin_divisor
        total_revenue = price_per_piece * total_pieces

        platform_fees = total_revenue * (platform_fee_pct / Decimal(100)) + fixed_fee

        net_profit = total_revenue - total_cost - platform_fees
        profit_per_piece = net_profit / total_pieces

        return {
            "electricity_cost": electricity_cost,
            "material_cost": material_cost,
            "labor_cost": labor_cost,
            "design_cost": design_cost,
            "machine_cost": machine_cost,
            "packaging_cost": packaging_cost,
            "shipping_cost": shipping_cost,
            "failure_buffer": failure_buffer,
            "subtotal_cost": subtotal_with_buffer,
            "overhead": overhead,
            "total_cost": total_cost,
            "cost_per_piece": cost_per_piece,
            "price_per_piece": price_per_piece,
            "total_revenue": total_revenue,
            "platform_fees": platform_fees,
            "net_profit": net_profit,
            "profit_per_piece": profit_per_piece,
        }
