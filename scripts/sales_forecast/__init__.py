"""HealthCore — Modelo de pronóstico de ventas (sales forecast).

Paquete con la lógica reutilizable del modelo:

    data.py      Carga, limpieza, features causales y split 8/2 sin fuga.
    metrics.py   MSE, RMSE, PSI, Gini predictivo y K2 Score (R²).
    model.py     Selección y entrenamiento de XGBoost + validación temporal.
    visualize.py Genera la gráfica con banda de variabilidad.
"""

__all__ = ["data", "metrics", "model", "visualize"]