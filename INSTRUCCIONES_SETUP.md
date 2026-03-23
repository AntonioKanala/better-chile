# Instrucciones de Setup — Better Chile

## Paso 1: Actualizar esquema de base de datos

**Acción:** Ejecutar SQL en Supabase Dashboard

1. Abre https://supabase.com/dashboard
2. Selecciona proyecto `mconaxbaemtkhjjgxcrb`
3. Ve a **SQL Editor** (menú izquierdo)
4. Pega TODO el contenido del archivo `setup_db.sql`
5. Haz clic en **Run** (Ctrl+Enter)

**Resultado esperado:**
```
Success. No rows returned.
```

Esto creará/actualizará las 4 tablas principales:
- ✅ `regulaciones` (expandida con nuevos campos)
- ✅ `dependencias` (nueva)
- ✅ `reportes` (nueva)
- ✅ `estadisticas` (nueva)

## Paso 2: Verificar tablas creadas

Ejecuta este query en SQL Editor:

```sql
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

Deberías ver al menos:
- `dependencias`
- `regulaciones`
- `reportes`
- `estadisticas`

## Paso 3: Verificar registros existentes

```sql
SELECT COUNT(*) as total FROM regulaciones;
```

Deberías ver ~12 registros (los que ya cargamos antes).

## Paso 4: Migrar datos de tabla `normas` antigua (si existe)

**Solo ejecutar si tienes datos en `normas` que quieras migrar:**

```sql
INSERT INTO regulaciones (
    id_norma, titulo, fecha_publicacion, texto_bruto, evaluado,
    verdict, summary, reason, created_at
)
SELECT
    id_norma,
    titulo,
    fecha AS fecha_publicacion,
    texto_limpio AS texto_bruto,
    evaluado,
    CASE
        WHEN evaluacion IS NOT NULL THEN evaluacion->>'verdict'
        WHEN veredicto IS NOT NULL THEN veredicto
        ELSE NULL
    END AS verdict,
    evaluacion->>'summary' AS summary,
    evaluacion->>'reason' AS reason,
    created_at
FROM normas
WHERE id_norma NOT IN (SELECT id_norma FROM regulaciones)
ON CONFLICT (id_norma) DO NOTHING;
```

## Paso 5: Verificar vistas creadas

```sql
SELECT * FROM v_stats_global;
```

Deberías ver estadísticas agregadas de las normas.

---

## Próximos pasos

Una vez completado el setup:

1. ✅ Probar ingestión masiva: `python scraper_leychile.py --desde-csv leyes_por_tema.csv --cantidad 100`
2. ✅ Probar evaluador actualizado: `python evaluador.py --limite 5`
3. ✅ Ejecutar Fase 1 completa (4,453 leyes)

---

**Última actualización:** 2026-03-09
