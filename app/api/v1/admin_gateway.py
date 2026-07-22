"""Admin API for gateway management — provider toggles, route overrides, strategy changes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.api.v1.schemas import ProviderToggle, RouteOverride, StrategyOverride
from app.auth import AuthContext, get_auth_context, require_role
from app.gateway.budget import budget_controller
from app.gateway.registry import registry
from app.gateway.router import router as gateway_router
from app.gateway.telemetry import cost_tracker

logger = logging.getLogger(__name__)
router = APIRouter()

_admin_deps = [Depends(require_role("admin"))]


@router.post("/override", dependencies=_admin_deps)
async def set_route_override(override: RouteOverride, auth: AuthContext = Depends(get_auth_context)):
    """Force a specific provider:model for a route."""
    logger.info(f"Admin {auth.user_id} overriding route {override.route} -> {override.provider}")
    if override.route and override.provider:
        gateway_router.set_manual_override(override.route, override.provider, override.model or "")
        return {"status": "override_set", "route": override.route, "provider": override.provider}
    else:
        gateway_router.clear_manual_override(override.route)
        return {"status": "override_cleared", "route": override.route}


@router.delete("/override/{route}", dependencies=_admin_deps)
async def clear_route_override(route: str, auth: AuthContext = Depends(get_auth_context)):
    """Clear manual override and return to auto-routing."""
    logger.info(f"Admin {auth.user_id} cleared override for {route}")
    gateway_router.clear_manual_override(route)
    return {"status": "auto_routing_restored", "route": route}


@router.post("/toggle-provider", dependencies=_admin_deps)
async def toggle_provider(toggle: ProviderToggle, auth: AuthContext = Depends(get_auth_context)):
    """Enable or disable an entire provider."""
    logger.info(f"Admin {auth.user_id} toggled {toggle.provider_name} -> {'enabled' if toggle.enabled else 'disabled'}")
    registry.switch_provider_state(toggle.provider_name, toggle.enabled)
    return {"status": f"provider_{'enabled' if toggle.enabled else 'disabled'}", "provider": toggle.provider_name}


@router.post("/strategy", dependencies=_admin_deps)
async def set_strategy(strategy: StrategyOverride, auth: AuthContext = Depends(get_auth_context)):
    """Override the switching strategy globally or per route."""
    logger.info(f"Admin {auth.user_id} set strategy {strategy.strategy} for route {strategy.route or 'global'}")
    if strategy.route:
        gateway_router.set_route_strategy(strategy.route, strategy.strategy)
    else:
        gateway_router.set_global_strategy(strategy.strategy)
    return {"status": f"strategy_set_to_{strategy.strategy}", "route": strategy.route or "global"}


@router.get("/status", dependencies=_admin_deps)
async def gateway_status(auth: AuthContext = Depends(get_auth_context)):
    """Full gateway status dashboard. Admin-only."""
    return {
        "overrides": gateway_router.get_active_overrides(),
        "strategies": gateway_router.get_active_strategies(),
        "provider_health": registry.get_stats(),
        "budget": budget_controller.current_status(),
        "telemetry": cost_tracker.daily_summary(),
    }
