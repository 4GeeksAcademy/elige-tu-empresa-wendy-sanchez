# Project Brief

## Resumen del proyecto
Este repositorio implementa entregables progresivos para el escenario empresarial de HealthCore (red de clínicas ambulatorias en EE. UU. y Reino Unido) dentro del track AI Engineering de 4Geeks Academy.

El proyecto combina tres frentes:
- Hito Web y Fundamentos: sitio público bilingüe (EN/ES), formulario de consulta de pacientes y utilidades TypeScript para lógica operativa.
- Hito Next.js (Talent Pipeline Tracker): interfaz para gestionar candidaturas de RR. HH. conectada a API.
- Hito Backend (Directorio de Proveedores): API FastAPI + TinyDB + Pydantic y su interfaz en el backoffice, solicitada por Diane Foster y Claire Whitfield.

## Descripcion del negocio
HealthCore opera 12 clínicas ambulatorias y busca digitalizar procesos críticos. El problema inicial abordado en este repo es la falta de presencia digital creíble y la captura no estructurada de consultas de pacientes, que impacta conversión, experiencia del paciente y carga operativa en recepción.

En paralelo, se trabaja en digitalización interna para People/HR con un tracker de pipeline de talento para reducir fricción en reclutamiento y seguimiento de candidatos.

## Objetivos del proyecto
1. Publicar una landing page profesional y bilingüe alineada al contexto de negocio.
2. Capturar consultas de pacientes con validaciones robustas para reducir errores y tiempo de triaje.
3. Implementar utilidades TypeScript puras para analítica operativa (claims, no-shows, CME, búsqueda y validación de datos).
4. Construir una UI Next.js para gestionar candidatos con listado, filtros, detalle, actualización de estado/etapa y gestión de notas.
5. Mantener estandares técnicos: tipado estricto, separación por responsabilidades y UX clara en estados de carga/error/éxito.
6. Centralizar el directorio de proveedores en una API con validación estricta y trazabilidad de cambios de tarifa para auditorías de cumplimiento.

## Problema que resuelve
- Externo (pacientes): corrige una presencia digital insuficiente y permite intake estructurado de consultas.
- Interno (operaciones/HR): centraliza y agiliza gestión de información operativa y de reclutamiento.
- Cumplimiento: da visibilidad de qué proveedores tienen acuerdos BAA/DPA firmados y conserva el histórico de la relación contractual.
- Técnico: establece una base escalable de utilidades y componentes para siguientes hitos (backend, telemetria, RAG, agentes, workflows).
