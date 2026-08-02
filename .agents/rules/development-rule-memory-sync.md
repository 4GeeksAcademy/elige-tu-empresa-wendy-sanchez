# Regla de desarrollo: sincronizacion de memoria y codigo

## Alcance de aplicacion
Tipo de alcance: siempre activa.

Nota: esta regla pertenece a .agents/ (configuracion de la herramienta de desarrollo), no a agents/ ni skills/ de producto.

## Regla
Despues de cualquier cambio funcional o estructural relevante, el agente debe verificar si el banco de memoria requiere actualizacion.

## Aplicacion minima
- Actualizar memory-bank/activeContext.md cuando cambie el comportamiento actual del sistema.
- Actualizar memory-bank/progress.md cuando cambie el estado de avance, riesgos o proximos pasos.
- Si no hay impacto documental, dejar constancia en el resumen final de que no fue necesaria actualizacion.

## Criterios de cumplimiento
1. La documentacion refleja fielmente el estado actual del codigo.
2. No quedan contradicciones entre memoria y repositorio.
3. La trazabilidad del cambio queda explicita en la respuesta final del agente.
