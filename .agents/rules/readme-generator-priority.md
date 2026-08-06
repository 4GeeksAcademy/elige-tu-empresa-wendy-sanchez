# Regla de desarrollo: prioridad para readme-generador

## Alcance de aplicacion
Tipo de alcance: siempre activa.

## Objetivo
Asegurar que el agente use la skill readme-generador como primera opcion cuando la solicitud del usuario sea crear, escribir, generar o actualizar README.

## Condiciones de activacion
Activar esta regla cuando la solicitud incluya README y verbos como:
- crear
- escribir
- generar
- actualizar
- redactar

## Condiciones de no activacion
No aplicar esta regla cuando la solicitud sea sobre:
- documentacion API
- changelog o registro de cambios
- entradas de blog

## Comportamiento requerido
1. Revisar si existe .agents/skills/readme-generador/SKILL.md.
2. Aplicar las reglas de esa skill antes de proponer o editar contenido.
3. Si ya existe README.md, leerlo y preservar secciones personalizadas.
4. No inventar comandos, puertos, versiones o licencias.
5. Si faltan datos, incluir una seccion breve de Pendiente por definir.

## Criterio de cumplimiento
- El resultado final mantiene consistencia con el codigo y configuracion real del repositorio.
- El README generado o actualizado conserva secciones personalizadas existentes.
