# Copilot Instructions

## Rol
Actúa como **desarrollador full stack y frontend senior**.

## Acceptance Criteria

### 1) Estructura y Semántica HTML
- El HTML usa etiquetas semánticas apropiadas en lugar de `<div>` genéricos.
- Todas las imágenes tienen atributos `alt` descriptivos.
- Los formularios usan `<label>` correctamente asociados con inputs.
- El marcado Schema.org está presente y correctamente implementado.
- La estructura del documento es lógica y jerárquica.

### 2) Diseño Responsive y Tailwind
- El sitio es completamente responsive (se adapta a móvil, tablet y escritorio).
- Existe un comando documentado y funcional, compatible con Codespaces, para ejecutar el proyecto localmente con `npx`.
- Se usa diseño mobile-first.
- Todos los estilos usan clases utilitarias de Tailwind.
- Los breakpoints de Tailwind (`sm:`, `md:`, `lg:`) se usan apropiadamente.
- No hay CSS personalizado innecesario (solo Tailwind).
- El diseño es visualmente coherente y profesional.
- El rendimiento se verifica en la URL pública con PageSpeed Insights con una puntuación mínima de 80 (ideal: por encima de 90).

### 3) Accesibilidad
- Todos los elementos interactivos son accesibles por teclado.
- Los atributos ARIA se usan donde mejoran la accesibilidad.
- El contraste de colores cumple con estándares mínimos.
- La navegación es lógica y predecible.
- Los mensajes de error son anunciados apropiadamente.

### 4) Formulario y Validación
- Todos los campos especificados en `CONTEXT.md` están presentes.
- Los tipos de input son apropiados para cada campo.
- La validación con JavaScript funciona correctamente para todos los campos.
- Los mensajes de error son específicos y útiles (no solo "campo inválido").
- La validación previene el envío de datos incorrectos.
- Los estados visuales del formulario son claros (foco, error, éxito).
- El botón de limpiar formulario funciona correctamente.

### 5) Adherencia al Contexto
- La landing page refleja fielmente el tipo de empresa y sector especificado en `CONTEXT.md`.
- El contenido presenta la experiencia y ventajas competitivas de la empresa.
- Los campos del formulario coinciden exactamente con los requeridos en `CONTEXT.md`.
- Cualquier regla de validación específica del dominio está implementada.
- El tono y contenido son coherentes con una empresa establecida que se digitaliza.

### 6) Corrección Técnica
- Las interfaces TypeScript modelan correctamente las entidades especificadas en el `CONTEXT.md` con todos sus campos y tipos.
- Las funciones de filtrado devuelven correctamente los elementos que cumplen los criterios especificados.
- El ordenamiento funciona correctamente en orden ascendente y descendente.
- La búsqueda lineal encuentra elementos en arrays desordenados sin errores.
- La búsqueda binaria funciona correctamente en arrays ordenados y devuelve el índice correcto o `-1` si no se encuentra.
- Las agregaciones calculan correctamente totales, promedios, conteos y valores extremos.
- Las validaciones rechazan datos que no cumplen con las reglas de negocio del `CONTEXT.md`.
- No hay errores de compilación de TypeScript en ningún archivo.
- Existe un comando documentado para validar o ejecutar TypeScript en local (ejemplo: `npx tsc --noEmit` o `npm run typecheck`).

### 7) Estructura y Organización
- El código está organizado en archivos separados por responsabilidad (types, utils, validations).
- Cada función tiene una única responsabilidad claramente identificable.
- Los nombres de variables, funciones e interfaces son descriptivos y siguen las convenciones de TypeScript.

### 8) Adaptación al Contexto
- Todos los nombres de entidades, campos y tipos coinciden exactamente con los especificados en el `CONTEXT.md`.
- Las validaciones implementadas corresponden a las reglas de negocio definidas en el `CONTEXT.md`.
- Los reportes generados responden a las necesidades específicas descritas en el `CONTEXT.md`.

### 9) Calidad de Código
- Las funciones son puras: no dependen de variables externas ni modifican estado global.
- Se manejan correctamente casos límite: arrays vacíos, elementos no encontrados, valores nulos.
- El código sigue las mejores prácticas de TypeScript: tipos explícitos, uso de `const`/`let` apropiado, evita `any`.
