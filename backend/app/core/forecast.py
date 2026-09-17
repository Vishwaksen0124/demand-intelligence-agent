from __future__ import annotations

from statistics import mean, pstdev

from .models import ForecastResult, SalesPoint


def _trend(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return (values[-1] - values[0]) / max(len(values) - 1, 1)


def calculate_forecast(product_id: str, history: list[SalesPoint], horizon_days: int = 7) -> ForecastResult:
    if horizon_days < 1:
        raise ValueError("forecast horizon must be at least 1 day")
    values = [point.units for point in history]
    recent = values[-14:] if len(values) >= 14 else values
    base = mean(recent) if recent else 0.0
    slope = _trend(recent) if recent else 0.0
    daily_forecast = [max(0.0, base + slope * step) for step in range(1, horizon_days + 1)]
    forecast_7_day = float(sum(daily_forecast[:7]))

    prior = values[-28:-14] if len(values) >= 28 else values[: max(len(values) - len(recent), 0)]
    trend = 0.0 if not prior or mean(prior) == 0 else (mean(recent) - mean(prior)) / mean(prior)
    volatility = pstdev(values[-14:]) if len(values) > 1 else 0.0
    confidence = max(0.4, min(0.95, 0.55 + min(len(values), 90) / 250 - volatility / 80))

    seasonality = "weekly" if len(values) >= 28 and sum(values[-7:]) != sum(values[-14:-7]) else "none"
    explanation = (
        f"Recent demand averages {base:.1f} units/day with trend {trend:+.1%}. "
        f"Confidence is {confidence:.0%} and seasonality is {seasonality}."
    )

    return ForecastResult(
        product_id=product_id,
        forecast_horizon=horizon_days,
        forecast_quantity=float(sum(daily_forecast)),
        history_days=len(values),
        trend=trend,
        seasonality=seasonality,
        confidence=confidence,
        daily_forecast=daily_forecast,
        forecast_7_day=forecast_7_day,
        explanation=explanation,
    )
