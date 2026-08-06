# AGENTS

## Objetivo
Este archivo define las reglas operativas del agente para trabajar en este repositorio de forma consistente, segura y trazable.

## 1) Lectura obligatoria al iniciar cada sesión
Al inicio de cada sesión, el agente debe leer y usar estos archivos del banco de memoria en el siguiente orden:

1. memory-bank/projectBrief.md
2. memory-bank/productContext.md
3. memory-bank/systemPattern.md
4. memory-bank/techContext.md
5. memory-bank/activeContext.md
6. memory-bank/progress.md

Regla de uso:
- Si hay conflicto entre estos documentos y el código fuente, el agente debe priorizar el estado real del código y actualizar la documentación correspondiente.

## 2) Flujo obligatorio antes de cada commit
Antes de crear un commit, el agente debe ejecutar este flujo mínimo en orden estricto:

1. Verificación de alcance:
- Confirmar que los cambios resuelven exactamente la solicitud y no incluyen modificaciones no relacionadas.

2. Revisión de impacto:
- Revisar archivos modificados, validar riesgos funcionales y comprobar que no se alteraron rutas protegidas sin autorización.

3. Validación técnica local:
- Ejecutar validaciones aplicables (como mínimo typecheck en raíz y, si aplica, en uis/talent-pipeline-tracker).
- Comandos base:
  - npm run typecheck
  - cd uis/talent-pipeline-tracker && npm run typecheck

4. Auto-revisión de calidad:
- Comprobar mensajes de error, accesibilidad básica de formularios tocados, consistencia de tipos y ausencia de hardcodes de secretos.

5. Actualización de memoria de proyecto:
- Si el cambio afecta contexto activo o roadmap, actualizar memory-bank/activeContext.md y/o memory-bank/progress.md.

6. Evidencia y preparación del commit:
- Resumir qué se cambió, qué se validó y resultados.
- Solo después de lo anterior, proceder con commit.

## 3) Rutas que no se deben modificar sin confirmación explícita del desarrollador
El agente no debe editar estas rutas sin aprobación explícita previa:

- CONTEXT.md
- company-choice.md
- .github/
- infra/
- internal/
- mcps/
- workflows/
- package-lock.json
- uis/talent-pipeline-tracker/AGENTS.md

Regla adicional:
- Si una tarea requiere cambiar una ruta protegida, el agente debe detenerse y solicitar confirmación antes de editar.

## 4) Distinción entre configuración del agente y código de producto
- .agents/ es el directorio de configuración del agente de desarrollo (reglas y skills operativas para Cursor, Windsurf, Claude Code u otras herramientas similares).
- Estructura esperada en este repositorio:
  - .agents/rules/<rule-name>.md
  - .agents/skills/<skill>/SKILL.md
- agents/ y skills/ son carpetas de producto del monorepo para construir agentes e integraciones de la empresa en hitos posteriores.
- El agente no debe mezclar objetivos ni mover archivos entre estos contextos sin instrucción explícita del desarrollador.
