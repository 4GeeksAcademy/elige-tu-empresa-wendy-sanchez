---
name: readme-generator
description: Genera un README del proyecto a partir del código. Úsalo cuando se solicite crear, escribir o generar un README. No usar para documentación API, registros de cambios o entradas de blog.
---

# README Generator

Genera o actualiza `README.md` en la raíz del proyecto a partir del código y configuración detectada.

## Disparadores (Triggers)

### Disparadores positivos
- Solicitudes que incluyan verbos como `crear`, `escribir` o `generar` en combinación con `README`.
- Solicitudes para redactar el archivo principal de documentación del proyecto.

### Disparadores negativos
- No activar para `documentación API`.
- No activar para `registros de cambios` (changelog).
- No activar para `entradas de blog`.

## Reglas para IA

1. Detectar la pila tecnológica leyendo el directorio raíz y archivos como `package.json`, `requirements.txt` o equivalentes.
2. Recopilar nombre del proyecto, descripción, instalación, uso y licencia desde archivos reales del repositorio.
3. Si ya existe `README.md`, leerlo antes de escribir y conservar secciones personalizadas que no estén en la plantilla base.
4. No inventar comandos, versiones, puertos o licencias. Si falta información, usar una sección breve de "Pendiente por definir".
5. Escribir contenido claro, escaneable y consistente con el stack detectado.
6. Mantener el README enfocado en uso del proyecto, no en documentación de API detallada.

## Flujo recomendado

1. Inspeccionar la raíz del proyecto.
2. Identificar stack, comandos y punto de entrada.
3. Extraer metadatos del proyecto (nombre, descripción, licencia, scripts).
4. Redactar README con plantilla estándar.
5. Si existe README previo, fusionar y preservar secciones personalizadas.
6. Guardar `README.md` en la raíz.

## Plantilla base

```markdown
# Nombre del Proyecto

Descripción breve de lo que hace el proyecto y para quién es.

## Configuración

Pasos para instalar dependencias y preparar el entorno.

## Uso

Ejemplo básico de ejecución o punto de entrada.

## Contribución

Guía breve para contribuir al proyecto.

## Licencia

Tipo de licencia del proyecto.
```

## Ejemplos Correcto/Incorrecto

### Incorrecto

```text
- Sobrescribir README.md sin leer su contenido actual.
- Inventar comandos de instalación no presentes en el proyecto.
- Eliminar una sección personalizada existente (por ejemplo, "Arquitectura interna") por no estar en la plantilla.
```

### Correcto

```text
- Leer README.md existente y conservar secciones personalizadas.
- Detectar scripts reales en package.json y usarlos en "Configuración" y "Uso".
- Si la licencia no aparece en archivos del repo, indicar "Pendiente por definir" en vez de inventarla.
```

## Referencias de apoyo

Usar estos README como referencia de estructura, tono y nivel de detalle:

- https://raw.githubusercontent.com/Azure-Samples/serverless-chat-langchainjs/refs/heads/main/README.md
- https://raw.githubusercontent.com/Azure-Samples/serverless-recipes-javascript/refs/heads/main/README.md
- https://raw.githubusercontent.com/sinedied/run-on-output/refs/heads/main/README.md
- https://raw.githubusercontent.com/sinedied/smoke/refs/heads/main/README.md
