# PLAN MAESTRO: BETTER CHILE
## Sistema Integral de Evaluación y Reforma Legislativa

**Objetivo:** Crear un sistema automatizado para evaluar toda la legislación chilena desde principios de libre mercado, identificar regulaciones a derogar/modificar/mantener, y generar reportes accionables para el gobierno.

**Inspiración:** Reforma argentina "Ley Bases" (672 regulaciones derogadas en 1 año) adaptada a Chile con análisis IA profundo.

---

## 📊 DIMENSIONAMIENTO DEL PROBLEMA

### Legislación Chilena — Datos Concretos

| Concepto | Cantidad |
|----------|----------|
| **Normas totales BCN** | ~347,000+ |
| **Leyes vigentes estimadas** | ~4,500-5,000 |
| **Leyes nuevas/año (2024)** | ~118 leyes |
| **Normas totales/año** | ~3,000 (incluyendo decretos, resoluciones) |
| **Categorías temáticas** | 180 (del CSV `leyes_por_tema.csv`) |

### Tipos de Normas en Chile (por jerarquía)

1. **Constitución Política**
2. **Leyes Orgánicas Constitucionales (LOC)**
3. **Leyes de Quórum Calificado (LQC)**
4. **Leyes Ordinarias** ← *FOCO PRINCIPAL*
5. **Decretos con Fuerza de Ley (DFL)**
6. **Decretos Ley (DL)** (período 1973-1990)
7. **Decretos Supremos (DS)**
8. **Resoluciones, Circulares, Ordenanzas**

### Referencia Argentina: Ley Bases 27.742

| Métrica | Valor |
|---------|-------|
| Artículos totales | 238 |
| Títulos temáticos | 10 |
| Leyes derogadas completamente | 32 |
| Leyes modificadas parcialmente | 19 |
| Decretos derogados | 6 |
| Regulaciones eliminadas (año 1) | **672** |
| Reparticiones públicas eliminadas | **450** |

---

## 🎯 ARQUITECTURA DEL SISTEMA

### Base de Datos: 4 Tablas

#### 1. `regulaciones` (tabla principal)
```sql
CREATE TABLE regulaciones (
    -- Identificación
    id_norma       TEXT PRIMARY KEY,
    tipo_norma     TEXT NOT NULL,        -- Ley, DFL, DL, Decreto, Resolución
    numero         TEXT,
    titulo         TEXT NOT NULL,
    fecha_publicacion TEXT,
    organismo      TEXT,                 -- Ministerio emisor
    categoria      TEXT,                 -- Tema/categoría (180 categorías del CSV)
    texto_bruto    TEXT NOT NULL,        -- Texto legal completo sin etiquetas

    -- Estado de procesamiento
    evaluado       BOOLEAN DEFAULT FALSE,
    evaluated_at   TIMESTAMPTZ,

    -- Evaluación IA (campos expandidos)
    verdict        TEXT,                 -- keep / modify / delete
    summary        TEXT,
    reason         TEXT,
    negative_effects TEXT,               -- Efectos secundarios nocivos
    legislative_action TEXT,             -- Acción concreta recomendada
    impact_areas   TEXT[],               -- Áreas afectadas

    -- Métricas de priorización
    impacto_economico TEXT,              -- alto / medio / bajo
    complejidad_burocracia TEXT,         -- alta / media / baja
    prioridad      INTEGER,              -- 1-10 (10 = urgente eliminar)
    categoria_reforma TEXT,              -- desregulación / simplificación / modernización / mantener

    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_regulaciones_categoria ON regulaciones(categoria);
CREATE INDEX idx_regulaciones_verdict ON regulaciones(verdict);
CREATE INDEX idx_regulaciones_evaluado ON regulaciones(evaluado);
CREATE INDEX idx_regulaciones_prioridad ON regulaciones(prioridad DESC);
```

#### 2. `dependencias` (grafo de referencias legales)
```sql
CREATE TABLE dependencias (
    id_norma_origen  TEXT REFERENCES regulaciones(id_norma),
    id_norma_destino TEXT,            -- Puede no estar en nuestra DB
    tipo_referencia  TEXT,            -- 'modifica', 'deroga', 'complementa', 'referencia'
    texto_contexto   TEXT,            -- Fragmento donde aparece la referencia
    PRIMARY KEY (id_norma_origen, id_norma_destino, tipo_referencia)
);

CREATE INDEX idx_dep_origen ON dependencias(id_norma_origen);
CREATE INDEX idx_dep_destino ON dependencias(id_norma_destino);
```

#### 3. `reportes` (documentos generados)
```sql
CREATE TABLE reportes (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo           TEXT NOT NULL,    -- 'resumen_ejecutivo', 'por_categoria', 'proyecto_ley'
    categoria      TEXT,
    titulo         TEXT NOT NULL,
    contenido      JSONB NOT NULL,
    formato        TEXT,              -- 'json', 'markdown', 'csv'
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
```

#### 4. `estadisticas` (métricas agregadas)
```sql
CREATE TABLE estadisticas (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo           TEXT NOT NULL,    -- 'por_categoria', 'por_organismo', 'por_año', 'global'
    clave          TEXT,              -- Subcategoría o filtro
    datos          JSONB NOT NULL,    -- Métricas flexibles
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stats_tipo ON estadisticas(tipo);
```

---

## 🚀 FASES DE IMPLEMENTACIÓN

### **FASE 0: Unificación y Consolidación** (1 día)

**Estado actual:**
- ✅ Tabla `regulaciones` existe (12 leyes guardadas)
- ⚠️ Tabla `normas` existe con 5 leyes + evaluaciones antiguas
- ⚠️ Scripts usan tablas diferentes (`scraper` → `regulaciones`, `evaluador` → `normas`)

**Tareas:**

1. **Migrar datos de `normas` → `regulaciones`**
   ```sql
   INSERT INTO regulaciones (id_norma, titulo, fecha_publicacion, texto_bruto, evaluado, verdict, summary, reason)
   SELECT id_norma, titulo, fecha, texto_limpio, evaluado,
          evaluacion->>'verdict', evaluacion->>'summary', evaluacion->>'reason'
   FROM normas
   ON CONFLICT (id_norma) DO NOTHING;
   ```

2. **Actualizar `setup_db.sql`** con esquema completo de 4 tablas

3. **Adaptar `evaluador.py`:**
   - Cambiar tabla `normas` → `regulaciones`
   - Cambiar campos: `texto_limpio` → `texto_bruto`, `fecha` → `fecha_publicacion`
   - Expandir JSON de respuesta con nuevos campos

**Output:** Sistema unificado usando solo tabla `regulaciones` + nuevos campos expandidos.

---

### **FASE 1: Ingestión Masiva** (2-3 días)

**Meta:** Poblar `regulaciones` con ~4,500 leyes chilenas.

#### Estrategia 1: CSV como fuente principal (más eficiente)

**Archivo:** `leyes_por_tema.csv`
- **Registros:** 4,453 leyes con categoría temática
- **Ventaja:** Ya tenemos `idNorma` + categoría → evitamos escaneos

**Script:** El scraper actual YA tiene `--desde-csv` implementado ✅

```bash
python scraper_leychile.py --desde-csv leyes_por_tema.csv --cantidad 500
```

**Lotes sugeridos:**
- Día 1: 500 leyes (validar calidad)
- Día 2: 2,000 leyes
- Día 3: 2,000 leyes restantes

#### Estrategia 2: Escaneo de rangos (complementaria)

Para normas NO en el CSV (DFL, DL recientes):

```bash
# Rango 2020-2025 (IDs ~1150000-1210000)
python scraper_leychile.py --rango 1200000 1210000 --todas
```

**Estimaciones:**
- Tiempo: ~4,500 leyes × 0.5s = ~37 min de descarga pura
- Con pausas y reintentos: ~2-3 horas por lote de 500
- **Total Fase 1: ~15-20 horas de ejecución distribuidas**

---

### **FASE 2: Evaluación Inteligente con IA** (4-7 días)

#### Nuevo Sistema de Veredictos (3 opciones vs 2)

| Veredicto | Significado | Criterio | Ejemplo Ley Bases |
|-----------|------------|----------|-------------------|
| **delete** | Derogar completamente | Regulación pura de mercado sin justificación de seguridad/derechos | Estatutos profesionales obsoletos (peluqueros, chóferes) |
| **modify** | Simplificar/modernizar | Objetivo válido pero implementación burocrática excesiva | Ley Hidrocarburos (48 arts. sustituidos, no derogada) |
| **keep** | Mantener sin cambios | Derechos fundamentales, Estado de Derecho, seguridad | Leyes contractuales, propiedad |

#### Prompt Mejorado: 6 Ejes de Evaluación

```
Evalúa la ley según estos ejes (inspirados en los 10 títulos de Ley Bases argentina):

1. LIBERTAD ECONÓMICA: ¿Restringe libre empresa, comercio, competencia?
2. BUROCRACIA ESTATAL: ¿Crea trámites, permisos, autorizaciones innecesarias?
3. COSTO FISCAL: ¿Genera gasto público sin retorno claro?
4. MODERNIZACIÓN: ¿Es obsoleta? ¿Hay tecnología/mecanismo mejor?
5. DUPLICACIÓN: ¿Se superpone con otras normas vigentes?
6. DERECHOS FUNDAMENTALES: ¿Protege derechos que deben preservarse?

Responde JSON con:
{
  "summary": "Qué hace la ley (2 oraciones)",
  "verdict": "keep | modify | delete",
  "reason": "Justificación económica/filosófica (2-3 oraciones)",
  "negative_effects": "Efectos secundarios nocivos (ej. barreras PYMES). 'Ninguno' si no hay.",
  "legislative_action": "Acción concreta (ej. 'Derogar arts. 5-12', 'Simplificar permisos a auto-declaración')",
  "impact_areas": ["Área1", "Área2"],
  "impacto_economico": "alto | medio | bajo",
  "complejidad_burocracia": "alta | media | baja",
  "prioridad": 1-10,
  "categoria_reforma": "desregulación | simplificación | modernización | mantener"
}
```

#### Procesamiento por Categorías (180 categorías)

**Ventaja:** El LLM ve contexto temático y detecta duplicaciones dentro de cada categoría.

```bash
# Evaluar todas las leyes de "Transporte"
python evaluador.py --categoria "Transporte"

# Evaluar todas (procesar en orden alfabético de categorías)
python evaluador.py --todas --batch-size 50

# Re-evaluar solo las de alta prioridad
python evaluador.py --re-evaluar --prioridad-min 8
```

**Optimización de costos:**
- Usar GPT-4o-mini para leyes cortas (<2000 chars): $0.15/$0.60 por 1M tokens
- Usar GPT-4o solo para leyes extensas (>10K chars): $2.50/$10 por 1M tokens

**Estimación de costo:**
- ~4,500 leyes × 8K tokens avg input × $1.5/M = **~$54 input**
- ~4,500 leyes × 800 tokens avg output × $7/M = **~$25 output**
- **Total estimado: ~$80 USD** (mezcla GPT-4o / GPT-4o-mini)

**Tiempo de procesamiento:**
- ~4,500 leyes × 2s API call = ~2.5 horas puras
- Con rate limits y pausas: **~6-8 horas** distribuidas en lotes

---

### **FASE 3: Análisis Cruzado y Priorización** (2-3 días)

#### Script 1: `analizador_dependencias.py` (nuevo)

**Objetivo:** Construir grafo de referencias entre normas.

**Lógica:**
```python
# Para cada ley en regulaciones:
#   1. Buscar menciones "Ley N° XXXXX" en texto_bruto
#   2. Extraer números de ley referenciadas
#   3. Clasificar tipo: "modifica", "deroga", "complementa", "referencia"
#   4. Insertar en tabla `dependencias`

# Ejemplo de patrón regex:
patron = r'(modifica|deroga|complementa).{0,50}Ley\s+N°\s*(\d+[\.\d]*)'
```

**Output:** Tabla `dependencias` poblada → permite:
- Identificar leyes "huérfanas" (no referenciadas por ninguna otra)
- Encontrar leyes "clave" (muy referenciadas → cuidado al derogar)
- Detectar cadenas de modificaciones (Ley A modifica B que modifica C)

#### Script 2: `analizador_duplicaciones.py` (nuevo)

**Objetivo:** Detectar superposiciones dentro de cada categoría.

**Técnica:**
- Agrupar leyes por `categoria`
- Calcular similitud semántica entre títulos/resúmenes (embeddings o TF-IDF)
- Si similitud > 80%, marcar como "posible duplicación"
- Generar reporte de pares candidatos para revisión manual

#### Script 3: `calculador_prioridad.py` (nuevo)

**Objetivo:** Rankear las 4,500 leyes por urgencia de reforma.

**Fórmula de prioridad:**
```python
score = (
    impacto_economico_peso[impacto_economico] * 0.4 +
    complejidad_burocracia_peso[complejidad_burocracia] * 0.3 +
    prioridad_llm * 0.3
)
# Pesos: alto=10, medio=5, bajo=2
```

**Output:**
- Top 100 leyes a derogar (verdict=delete, prioridad > 7)
- Top 50 leyes a modificar (verdict=modify, complejidad=alta)
- Lista de leyes "intocables" (verdict=keep, impacto=alto)

---

### **FASE 4: Generación de Reportes** (2 días)

#### Script: `generador_reportes.py` (nuevo)

**Reportes a generar:**

1. **Resumen Ejecutivo** (`reportes/resumen_ejecutivo.json`)
   ```json
   {
     "fecha": "2025-03-10",
     "leyes_evaluadas": 4453,
     "veredictos": {
       "delete": 892,
       "modify": 1567,
       "keep": 1994
     },
     "top_100_derogar": [...],
     "top_50_modificar": [...],
     "impacto_estimado": {
       "leyes_eliminadas": 892,
       "regulaciones_reducidas": "~40%"
     }
   }
   ```

2. **Informe por Categoría** (`reportes/por_categoria/*.md`)

   Ejemplo: `reportes/por_categoria/transporte.md`
   ```markdown
   # Análisis: Transporte (47 leyes)

   ## Resumen
   - Derogar: 12 leyes (25%)
   - Modificar: 23 leyes (49%)
   - Mantener: 12 leyes (26%)

   ## Top 5 a Derogar
   1. **Ley 18696** - Estatuto de conductores particulares
      - Razón: Regulación gremial obsoleta, Uber/apps ya reguladas
      - Prioridad: 9/10
   ...
   ```

3. **Proyecto de Ley Bases Chile** (`reportes/proyecto_ley_bases_chile.md`)

   Estructura estilo Ley 27.742 argentina:
   ```markdown
   # PROYECTO DE LEY: Bases y Puntos de Partida para la Libertad Económica de Chile

   ## Título I: Declaración de Emergencia Regulatoria
   Art. 1 - Declarar emergencia...

   ## Título II: Derogaciones Generales
   Art. 2 - Deróganse las siguientes leyes:
   1. Ley N° 12345 (Estatuto de...)
   2. Ley N° 23456 (...)
   ...

   ## Título III: Simplificación Administrativa
   Art. 15 - Sustitúyese el artículo 8 de la Ley N° 34567...
   ```

4. **Rankings CSV** (`reportes/rankings/*.csv`)
   - `top_100_derogar.csv`
   - `top_50_modificar.csv`
   - `leyes_por_organismo.csv` (ministerios con más regulación)
   - `leyes_por_impacto.csv`

---

### **FASE 5: Dashboard Web (Opcional — 1 semana)**

**Tech Stack Sugerido:**
- Frontend: Next.js + Tailwind CSS + shadcn/ui
- Backend: Supabase (ya configurado)
- Visualización: Recharts, React Flow (para grafo de dependencias)

**Páginas:**

1. **Home** — Métricas globales:
   - Total leyes evaluadas
   - Distribución de veredictos (gráfico de torta)
   - Top 10 categorías con más regulación

2. **Explorador** — Tabla filtrable:
   - Filtros: categoría, veredicto, organismo, año
   - Búsqueda por texto
   - Click en fila → modal con detalles completos

3. **Grafo de Dependencias** — Visualización interactiva:
   - Nodos = leyes
   - Aristas = referencias (color por tipo: modifica/deroga/etc.)
   - Click en nodo → info de la ley

4. **Reportes** — Descarga de documentos generados:
   - PDFs, JSONs, CSVs

**Deployment:** Vercel (frontend) + Supabase (backend) = gratis para MVP.

---

## 📈 CRONOGRAMA ESTIMADO

| Fase | Duración | Costo | Output |
|------|----------|-------|--------|
| **0. Unificación** | 1 día | $0 | Esquema consolidado en `regulaciones` |
| **1. Ingestión** | 2-3 días | $0 | ~4,500 leyes en DB |
| **2. Evaluación IA** | 4-7 días | **~$80** | Todas las leyes evaluadas con veredictos |
| **3. Análisis Cruzado** | 2-3 días | $0 | Grafos de dependencias, rankings |
| **4. Reportes** | 2 días | $0 | 4 tipos de documentos generados |
| **5. Dashboard (opcional)** | 5-7 días | $0 | Web app pública |
| **TOTAL** | **11-17 días** | **~$80** | Sistema completo operativo |

---

## 🎯 ENTREGABLES FINALES

### Para el Gobierno / Congreso

1. **Documento ejecutivo** (PDF, 20-30 págs):
   - Resumen de metodología
   - Top 100 leyes a derogar con justificaciones
   - Top 50 leyes a modificar con acciones concretas
   - Impacto estimado en reducción de burocracia

2. **Proyecto de Ley** (borrador legislativo):
   - Formato oficial de proyecto de ley chileno
   - Artículos de derogación agrupados por tema
   - Artículos de modificación/sustitución

3. **Datasets abiertos** (CSV/JSON):
   - `regulaciones_evaluadas.csv` — Todas las 4,500 leyes con veredictos
   - `ranking_prioridad.csv` — Ordenadas por urgencia
   - `dependencias.csv` — Grafo de referencias

### Para Medios / Opinión Pública

4. **Infografías**:
   - "Las 10 leyes más absurdas de Chile"
   - "Cómo reducir 40% de la burocracia en 6 meses"
   - Comparativa Chile vs Argentina (Ley Bases)

5. **Dashboard web público**:
   - Explorador interactivo de toda la legislación
   - Grafo de dependencias visualizado
   - Cada ciudadano puede buscar leyes que le afectan

---

## 🚨 RIESGOS Y MITIGACIONES

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| **Rate limits API** | Media | Bajo | Lotes pequeños (50 leyes), sleep entre requests |
| **Costo API excede presupuesto** | Baja | Medio | Usar GPT-4o-mini para leyes cortas, monitorear costos |
| **Calidad de evaluación IA inconsistente** | Media | Alto | Validación manual de muestra (100 leyes), re-prompting |
| **XML de BCN con errores** | Media | Bajo | Try-except robusto, logging de IDs fallidos |
| **Presión política contra el proyecto** | Media | Alto | Publicar dataset abierto ANTES de entregar al gobierno |

---

## 🔄 PRÓXIMOS PASOS INMEDIATOS

1. ✅ **Arreglar unificación de tablas** (Fase 0) — AHORA
2. ✅ **Probar ingestión CSV con 100 leyes** — HOY
3. ✅ **Ajustar evaluador con nuevo prompt** — HOY
4. ⏳ **Ejecutar Fase 1 completa** — Mañana

---

## 📚 REFERENCIAS

- [Ley Bases Argentina 27.742](https://www.boletinoficial.gob.ar/detalleAviso/primera/310189/20240708)
- [Biblioteca del Congreso Nacional Chile](https://www.bcn.cl/leychile/)
- [Ministerio de Desregulación Argentina](https://www.argentina.gob.ar/desregulacion)
- [CADEP - Desregulación y Eficiencia del Estado](https://cadep.ufm.edu/2025/01/desregulacion-y-eficiencia-del-estado/)

---

**Última actualización:** 2026-03-09
**Versión:** 1.0
**Autor:** Better Chile Team
