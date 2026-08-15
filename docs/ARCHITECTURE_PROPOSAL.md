# Propuesta de Arquitectura Backend para HealthCore

## 1. Contexto y criterio de decisión

HealthCore no es una startup SaaS genérica: es una red de 12 clínicas en dos jurisdicciones (EE. UU. y Reino Unido), con sistemas heredados distintos por país, requisitos de cumplimiento (HIPAA y UK GDPR), y un equipo tecnológico pequeño (6 personas) que debe entregar valor rápido sin aumentar riesgo operativo.

El backend debe resolver tres tensiones simultáneas:

1. Integrar dominios clínicos y operativos heterogéneos sin crear un "monolito espagueti".
2. Mantener trazabilidad y controles de cumplimiento por tratar datos sensibles de pacientes.
3. Permitir evolución incremental (nuevos módulos y automatizaciones) sin obligar a una migración temprana a microservicios.

## 2. Patrón arquitectónico propuesto

### Patrón elegido: Monolito modular con arquitectura en capas por dominio

La recomendación es un **monolito modular** que combina:

- **Separación por dominio** (módulos de negocio claros).
- **Capas internas** por módulo (API, aplicación, dominio, infraestructura).
- **Contratos explícitos** entre capas (DTOs/schemas y servicios).

No se propone MVC tradicional como patrón principal porque el núcleo del problema no es renderizado de vistas, sino integración de procesos sanitarios y operativos con reglas de negocio y cumplimiento. Tampoco se propone serverless puro como patrón base porque la carga principal de HealthCore exige integraciones persistentes, trazabilidad transversal y control fino de acceso a datos sensibles entre dominios y jurisdicciones.

### Justificación vinculada al negocio

1. **Equipo pequeño, complejidad de negocio alta**: un monolito modular reduce sobrecarga operativa frente a microservicios (menos despliegues, menos redes internas, menos observabilidad distribuida obligatoria), pero mantiene separación real de responsabilidades.
2. **Cumplimiento y auditoría**: centralizar políticas transversales (autenticación, autorización, auditoría, logging estructurado, trazas) en una sola aplicación facilita controles consistentes para HIPAA/UK GDPR.
3. **Integración incremental con legado**: cada dominio puede encapsular adaptadores hacia sistemas existentes (EHR, facturación, agendas) sin bloquear la entrega de otros dominios.
4. **Escalado progresivo**: si un dominio crece (por ejemplo, facturación o patient access), puede extraerse a servicio independiente más adelante porque los límites de módulo ya quedan definidos desde el inicio.

## 3. Estructura de carpetas y módulos backend propuesta

Ubicación sugerida en este monorepo:

- `services/healthcore-api/`

Estructura:

```text
services/
  healthcore-api/
    app/
      main.py
      api/
        deps.py
        v1/
          api.py
          routers/
            patient_access.py
            clinical_operations.py
            revenue_cycle.py
            compliance.py
            workforce.py
            executive_reporting.py
            health.py
      core/
        config.py
        security.py
        logging.py
        exceptions.py
      db/
        base.py
        session.py
        models/
          patient.py
          appointment.py
          claim.py
          clinician.py
          note.py
      schemas/
        patient.py
        appointment.py
        claim.py
        workforce.py
        common.py
      modules/
        patient_access/
          application/
            services.py
          domain/
            entities.py
            policies.py
          infrastructure/
            repositories.py
            ehr_adapter.py
            notifications_adapter.py
        clinical_operations/
          application/
          domain/
          infrastructure/
        revenue_cycle/
          application/
          domain/
          infrastructure/
        compliance/
          application/
          domain/
          infrastructure/
        workforce/
          application/
          domain/
          infrastructure/
        executive_reporting/
          application/
          domain/
          infrastructure/
      tests/
        unit/
        integration/
        contract/
    alembic/
    pyproject.toml
    .env.example
```

### Criterio de separación por responsabilidad

1. `api/`: capa de transporte HTTP (routers, dependencia de autenticación, serialización/deserialización).
2. `modules/*/application`: casos de uso (orquestación, transacciones, validaciones de flujo).
3. `modules/*/domain`: reglas de negocio puras y políticas (sin dependencias de framework).
4. `modules/*/infrastructure`: implementación técnica (SQLAlchemy, clientes externos, mensajería).
5. `core/`: capacidades transversales (configuración, seguridad, errores, logging).
6. `db/`: sesión, metadata y modelos de persistencia.
7. `schemas/`: contratos de entrada/salida para API.

Este corte evita mezclar reglas clínicas con detalles de infraestructura y permite pruebas unitarias de dominio sin levantar FastAPI.

## 4. Organización de endpoints y routers en FastAPI por dominio

### Principio de diseño

- Versionado por prefijo: `/api/v1`.
- Un router por dominio de negocio.
- Endpoints agrupados por recursos y acciones, no por tipo de operación técnica.
- Dependencias transversales en `api/deps.py` (auth, tenant, permisos, trazabilidad).

### Propuesta de routers y rutas

#### 4.1 Patient Access (`patient_access.py`)

Objetivo: captación y gestión de consultas/citas iniciales.

Rutas:

- `POST /api/v1/patient-access/inquiries`
- `GET /api/v1/patient-access/inquiries`
- `GET /api/v1/patient-access/inquiries/{inquiry_id}`
- `PATCH /api/v1/patient-access/inquiries/{inquiry_id}/status`
- `POST /api/v1/patient-access/appointments`
- `GET /api/v1/patient-access/appointments`

#### 4.2 Clinical Operations (`clinical_operations.py`)

Objetivo: operación clínica entre sedes.

Rutas:

- `GET /api/v1/clinical-operations/patients/{patient_id}/summary`
- `GET /api/v1/clinical-operations/clinics/{clinic_id}/schedule`
- `GET /api/v1/clinical-operations/no-show-risk`
- `POST /api/v1/clinical-operations/notes`

#### 4.3 Revenue Cycle (`revenue_cycle.py`)

Objetivo: reclamaciones, codificación y seguimiento de rechazo.

Rutas:

- `POST /api/v1/revenue-cycle/claims`
- `GET /api/v1/revenue-cycle/claims`
- `GET /api/v1/revenue-cycle/claims/{claim_id}`
- `PATCH /api/v1/revenue-cycle/claims/{claim_id}/status`
- `GET /api/v1/revenue-cycle/metrics/denial-rate`

#### 4.4 Compliance (`compliance.py`)

Objetivo: auditoría y solicitudes de datos de paciente.

Rutas:

- `GET /api/v1/compliance/audit-events`
- `POST /api/v1/compliance/data-access-requests`
- `GET /api/v1/compliance/data-access-requests/{request_id}`
- `GET /api/v1/compliance/risk-score`

#### 4.5 Workforce (`workforce.py`)

Objetivo: procesos de RR. HH. y formación CME.

Rutas:

- `POST /api/v1/workforce/candidates`
- `GET /api/v1/workforce/candidates`
- `GET /api/v1/workforce/candidates/{candidate_id}`
- `PATCH /api/v1/workforce/candidates/{candidate_id}`
- `GET /api/v1/workforce/cme/compliance`

#### 4.6 Executive Reporting (`executive_reporting.py`)

Objetivo: KPIs ejecutivos consolidados.

Rutas:

- `GET /api/v1/executive-reporting/kpis/weekly`
- `GET /api/v1/executive-reporting/kpis/by-clinic`
- `GET /api/v1/executive-reporting/alerts`

#### 4.7 Health (`health.py`)

Objetivo: operación y observabilidad.

Rutas:

- `GET /health`
- `GET /ready`
- `GET /live`

## 5. Investigación y convenciones habituales en FastAPI

La propuesta sigue convenciones ampliamente usadas en FastAPI, especialmente:

1. **"Bigger Applications" en documentación oficial de FastAPI**:
   - Separar `main.py`, routers, dependencias y submódulos.
   - Componer la API con `include_router`.
2. **Estructuras de referencia de comunidad (por ejemplo, full-stack-fastapi-template)**:
   - Agrupar rutas por dominio/recurso.
   - Separar `core` (configuración/seguridad), `models`, `schemas` y capa de acceso a datos.
   - Versionar rutas (`/api/v1`) para evolución sin ruptura.

Cómo influyen estas convenciones en esta propuesta:

- Se evita un archivo único de rutas porque en HealthCore crecería rápidamente y perdería trazabilidad.
- Se explicita la separación `schemas` vs `models` para desacoplar contrato API de persistencia.
- Se centraliza configuración y seguridad en `core/` para cumplir políticas regulatorias de forma homogénea.

## 6. Frontend y backend como sistemas separados

En este repositorio ya existe una separación funcional entre UIs y servicios. Para consolidarla:

### 6.1 Estrategia de repositorio

- **Corto/medio plazo**: mantener monorepo (ya existente) con límites claros entre `uis/` y `services/`.
- **Largo plazo (opcional)**: separar repositorios solo cuando haya equipos independientes con ciclos de release muy diferentes.

### 6.2 Comunicación por API

- Contrato HTTP/JSON versionado (`/api/v1`).
- OpenAPI como contrato fuente para frontend (idealmente generación de cliente tipado).
- Manejo consistente de errores (`code`, `message`, `details`, `trace_id`) para diagnósticos cruzados frontend-backend.

### 6.3 Variables de entorno

- Backend: secretos y configuración sensible en variables no públicas (`DB_URL`, `JWT_SECRET`, `EHR_API_KEY`, etc.).
- Frontend: solo variables públicas necesarias (por ejemplo `NEXT_PUBLIC_API_URL`).
- Política: `.env.example` documentado por servicio, sin credenciales reales en el repositorio.

### 6.4 CORS

- Configurar lista explícita de orígenes permitidos por entorno (dev/staging/prod).
- Prohibir comodines (`*`) en producción para endpoints con datos sensibles.
- Alinear CORS con estrategia de autenticación (cookies seguras o bearer token) para evitar fallos intermitentes y riesgos de exposición.

## 7. Riesgos y puntos de atención

1. **Riesgo de “monolito sin modularidad real”**
   - Qué puede salir mal: si el equipo mezcla lógica de negocio en routers o en utilidades globales, el sistema se vuelve difícil de probar y modificar; aumenta el tiempo de entrega y el riesgo de regresiones.
   - Mitigación: reglas de revisión que impidan lógica de negocio en la capa API y obliguen a casos de uso en `application/`.

2. **Riesgo de incumplimiento regulatorio por diseño inconsistente**
   - Qué puede salir mal: trazas incompletas de acceso a datos o políticas divergentes por módulo pueden derivar en incumplimiento HIPAA/UK GDPR.
   - Mitigación: auditoría transversal obligatoria, middleware de trazabilidad y controles de autorización centralizados.

3. **Riesgo de desacople incompleto frontend-backend**
   - Qué puede salir mal: cambios en payloads sin versionado rompen UIs; CORS mal configurado bloquea operaciones en producción.
   - Mitigación: versionado estricto de API, pruebas de contrato y matriz de orígenes por entorno automatizada en CI.

4. **Riesgo de extracción prematura a microservicios**
   - Qué puede salir mal: fragmentación temprana con equipo pequeño incrementa costo operativo (deploy, observabilidad, incidentes) sin resolver el problema de negocio.
   - Mitigación: mantener monolito modular hasta que métricas objetivas (carga, tiempos de despliegue, ownership por dominio) justifiquen separación.

## 8. Conclusión

La opción más sólida para HealthCore hoy es un monolito modular en capas por dominio dentro de FastAPI. Este enfoque responde al contexto real: alta complejidad regulatoria y operativa, múltiples sistemas heredados y necesidad de entrega incremental con un equipo reducido. La estructura propuesta no solo organiza código; reduce riesgo de cumplimiento, facilita mantenimiento y deja una ruta clara para escalar por dominios cuando el negocio lo exija.
