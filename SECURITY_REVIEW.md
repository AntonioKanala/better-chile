# Better Chile - Security Review

**Fecha:** 23 de Marzo de 2026
**Estado:** COMPLETO (análisis de riesgos + recomendaciones)

---

## 🔒 Resumen Ejecutivo

**Riesgo General:** BAJO-MEDIO

El proyecto es principalmente un **análisis de datos + reporte**, no un sistema financiero. Sin embargo, hay **3 áreas críticas de riesgo**:

1. **Supabase/Database** — Exposición de claves API
2. **OpenAI API** — Exposición de API keys
3. **Dashboard público** — XSS/CSRF vulnerabilities

**Todas tienen soluciones simples.**

---

## 1. DASHBOARD (React/Frontend)

### ✅ LO QUE ESTÁ BIEN

- **Supabase Anon Key:** Solo tiene permisos de lectura (`read`)
- **No hay formularios complejos** — Bajo riesgo de CSRF
- **Datos públicos** — Las normas no son sensibles
- **HTTPS en Vercel** — Automático, encriptado

### ⚠️ RIESGOS IDENTIFICADOS

#### 1.1 Exposición de Supabase Anon Key (BAJO)

**Riesgo:** La clave está en `dashboard/.env` y visible en variables de entorno

**Actual:**
```typescript
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';
```

**Problema:** Si alguien obtiene tu clave anon, puede:
- Leer toda la tabla `regulaciones` (ya es pública en el dashboard)
- Potencialmente listar otras tablas

**Solución (RECOMENDADA):**
```typescript
// dashboard/.env.example (versión pública)
VITE_SUPABASE_URL=https://mconaxbaemtkhjjgxcrb.supabase.co
VITE_SUPABASE_ANON_KEY=<tu_anon_key_aqui>

// En Vercel: Agregar como Environment Variable en settings
```

**Impacto:** BAJO — La clave anon es "pública" por diseño (para aplicaciones frontend)

---

#### 1.2 XSS en Búsqueda de Normas (BAJO)

**Riesgo:** Si alguien injecciona JavaScript en la búsqueda

**Actual:**
```typescript
const q = searchText.toLowerCase();
return n.titulo?.toLowerCase().includes(q) || n.summary?.toLowerCase().includes(q)
```

**Problema:** No hay escapar de HTML, pero React escapa automáticamente

**Estado:** ✅ SEGURO (React escapa por defecto)

---

#### 1.3 Acceso a Datos Privados en Buscador (BAJO)

**Riesgo:** ¿Puede alguien ver análisis privados en la búsqueda?

**Respuesta:** NO — El query solo busca en `evaluado=true`, no hay análisis profundo aún

**Estado:** ✅ SEGURO

---

### ✅ RECOMENDACIONES DASHBOARD

1. **Agregar `.env.example`** (sin claves reales)
2. **Documentar variables de entorno** en README
3. **Configurar CORS** en Supabase (opcional, ya está restrictivo)

```bash
# dashboard/.env.example
VITE_SUPABASE_URL=https://[project].supabase.co
VITE_SUPABASE_ANON_KEY=[paste_your_anon_key_here]
```

---

## 2. PYTHON SCRIPTS (Evaluador, Reportes)

### ⚠️ RIESGOS IDENTIFICADOS

#### 2.1 API Keys en .env (CRÍTICO)

**Riesgo:** Muy alto si `.env` está en Git

**Actual:**
```
SUPABASE_URL=https://...
SUPABASE_KEY=...
OPENAI_API_KEY=...
```

**Problema:** Si alguien obtiene `.env`, puede:
- Leer/escribir todo en Supabase
- Usar tu crédito de OpenAI
- Modificar evaluaciones

**Estado:** ✅ SEGURO (`.env` está en `.gitignore`)

**Verificar:**
```bash
cat .gitignore | grep .env
# Debe mostrar: .env
```

**Verificación adicional:**
```bash
git ls-files | grep .env
# No debe mostrar nada (significa .env no está en Git)
```

---

#### 2.2 Supabase Service Role Key (CRÍTICO)

**Riesgo:** Tienes la clave de servicio (puede escribir datos)

**Actual:**
```python
client = create_client(SUPABASE_URL, SUPABASE_KEY)  # Service Role Key
```

**Problema:** Si se expone, cualquiera puede:
- Modificar o borrar todas las normas
- Crear/eliminar tablas
- Acceder a datos internos

**Estado:** ⚠️ REQUIERE CUIDADO

**Recomendaciones:**
1. **NUNCA commits `.env` a Git**
2. **Usa variables de entorno en producción** (en Vercel/servidores)
3. **Limita permisos en Supabase**:
   - Crea un rol específico para `evaluador.py`
   - Solo permite `UPDATE` en columnas específicas
   - No permite `DELETE`

```sql
-- Crear rol restrictivo en Supabase
CREATE ROLE evaluador_role;
GRANT UPDATE (verdict, summary, reason, negative_effects, legislative_action,
             impact_areas, impacto_economico, complejidad_burocracia, prioridad,
             categoria_reforma, analisis_profundo, evaluacion_profunda)
ON regulaciones TO evaluador_role;
-- NO GRANT DELETE, DROP, ALTER
```

---

#### 2.3 OpenAI API Key (CRÍTICO)

**Riesgo:** Muy alto - cualquiera puede usar tu crédito

**Actual:**
```python
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.Client(api_key=api_key)
```

**Problema:** Alguien puede hacer millones de requests con tu crédito

**Estado:** ⚠️ REQUIERE MONITOREO

**Recomendaciones:**
1. **Monitorea costos en OpenAI dashboard** (alerta si > $50/mes)
2. **Usa rate limiting** en scripts
3. **No expongas API key** en logs
4. **Rota la clave regularmente** (cada 3 meses)

```python
# Verificar que NO logs la API key
print(f"Usando OpenAI key: {api_key[-10:]}")  # ✅ BIEN - solo últimos 10 chars
print(f"API Key: {api_key}")  # ❌ MAL - expone la clave
```

---

#### 2.4 SQL Injection (BAJO)

**Riesgo:** ¿Pueden inyectar SQL?

**Actual:**
```python
# ✅ SEGURO - Supabase usa prepared statements
client.table('regulaciones').select(...).eq('verdict', user_input).execute()

# No hay concatenación de strings en SQL
```

**Estado:** ✅ SEGURO

---

### ✅ RECOMENDACIONES PYTHON

1. **Crear `.env.example`:**
```bash
# .env.example (SIN valores reales)
SUPABASE_URL=https://[project].supabase.co
SUPABASE_KEY=your_service_role_key_here
OPENAI_API_KEY=sk-...your_key_here
```

2. **Documentar en README:**
```markdown
## Configuración de Seguridad

1. Nunca commits `.env` a Git
2. Las claves están protegidas en .gitignore
3. En producción, usa variables de entorno del servidor
4. Monitorea costos de OpenAI regularmente
```

3. **Agregar validación de claves:**
```python
def validate_env_vars():
    required = ['SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY']
    for var in required:
        if not os.getenv(var):
            raise ValueError(f"FALTA: {var} en .env")
    print("✓ Variables de entorno validadas")
```

---

## 3. SUPABASE (Database)

### ✅ LO QUE ESTÁ BIEN

- **Encriptación en tránsito** (HTTPS) — Automático
- **Encriptación en reposo** — Plan pago de Supabase
- **RLS (Row Level Security)** — Disponible
- **Backups automáticos** — Supabase lo hace

### ⚠️ RIESGOS IDENTIFICADOS

#### 3.1 Datos públicos sin RLS (BAJO)

**Riesgo:** Cualquiera con la clave anon puede leer todo

**Actual:**
```sql
-- Las tablas son accesibles sin restricción RLS
SELECT * FROM regulaciones;  -- Funciona para cualquiera
```

**Problema:** No es un "problema" porque los datos SON públicos (análisis legislativo)

**Estado:** ✅ ACEPTABLE (por diseño)

**Pero:** Si agregamos datos sensibles luego (ej: comentarios internos), necesitamos RLS

---

#### 3.2 Backups (BAJO)

**Riesgo:** ¿Qué pasa si Supabase se cae?

**Estado:** ✅ SUPABASE MANEJA

Supabase hace backups automáticos (plan pago). Si es plan gratis:
```sql
-- Crear backup manual
pg_dump -h db.supabase.co -U postgres -d postgres > backup.sql
```

---

### ✅ RECOMENDACIONES SUPABASE

1. **Activar RLS como mejor práctica:**
```sql
-- Habilitar Row Level Security en tabla
ALTER TABLE regulaciones ENABLE ROW LEVEL SECURITY;

-- Policy: Lectura pública
CREATE POLICY "regulaciones_read_public"
  ON regulaciones FOR SELECT
  USING (true);

-- Policy: Solo servicio puede escribir
CREATE POLICY "regulaciones_write_admin"
  ON regulaciones FOR UPDATE
  USING (auth.role() = 'service_role');
```

2. **Configurar backups (si plan pago)**
3. **Monitorear logs de acceso** en Supabase dashboard

---

## 4. OPENAI API

### ⚠️ RIESGOS IDENTIFICADOS

#### 4.1 Exposición de API Key (CRÍTICO)

**Ya cubierto en sección 2.3**

#### 4.2 Inyección de Prompts (BAJO)

**Riesgo:** ¿Puede alguien hackear el prompt?

**Actual:**
```python
# ✅ SEGURO - El prompt NO viene de usuario
SYSTEM_PROMPT = """
Eres un analista de políticas públicas...
"""

USER_PROMPT_TEMPLATE = """
Evalúa la siguiente norma:
{texto_norma}  # Viene de base de datos, no de usuario
"""
```

**Estado:** ✅ SEGURO

---

### ✅ RECOMENDACIONES OPENAI

1. **Monitorea costos** (alertas en $50+)
2. **Rota API key cada 3 meses**
3. **No loguees respuestas completas** (pueden contener datos sensibles)

```python
# ✅ BIEN - Log mínimo
log.info(f"[{id_norma}] Evaluado con veredicto: {verdict}")

# ❌ MAL - Log excesivo
log.info(f"[{id_norma}] Respuesta completa: {response.json()}")
```

---

## 5. VERCEL DEPLOYMENT

### ✅ LO QUE ESTÁ BIEN

- **HTTPS automático** ✅
- **DDoS protection** ✅
- **Environment variables secretas** ✅
- **No acceso directo a archivos .env** ✅

### ⚠️ RIESGOS IDENTIFICADOS

#### 5.1 Environment Variables Visibles (BAJO)

**Riesgo:** En Vercel Settings, las variables son visibles (pero encriptadas)

**Recomendación:** NO pongas API keys en Vercel
- Dashboard = solo **anon key** (lectura)
- Scripts Python = solo variables locales en `.env`

**Estado:** ✅ SEGURO (ya así lo tienes)

---

## 🎯 CHECKLIST DE SEGURIDAD

### INMEDIATO (hoy)

- [ ] Verificar `.env` NO está en Git
```bash
git status | grep .env  # No debe mostrar nada
```

- [ ] Crear `.env.example` sin valores reales
```bash
cp .env .env.example
# Editar .env.example y remover valores
git add .env.example
```

- [ ] Revisar `.gitignore` incluye `.env`
```bash
grep "\.env" .gitignore  # Debe mostrar: .env
```

### ESTA SEMANA

- [ ] Crear dashboard/env.example
- [ ] Documentar en README: "Security Considerations"
- [ ] Configurar alertas en OpenAI (si costo > $50)
- [ ] Agregar validación de variables en `evaluador.py`

### ESTE MES

- [ ] Crear rol restrictivo en Supabase (opcional, pero buena práctica)
- [ ] Implementar logging sin exponer claves
- [ ] Revisar logs de Supabase acceso
- [ ] Planificar rotación de API keys (próximo mes)

---

## 📋 CHECKLIST POR COMPONENTE

### Dashboard (React)
- [ ] Variables de entorno documentadas
- [ ] `.env.example` creado
- [ ] XSS preventado (React ya lo hace)
- [ ] CORS configurado (opcional)

### Python Scripts
- [ ] `.env.example` creado
- [ ] `.gitignore` incluye `.env`
- [ ] Logging sin exposición de claves
- [ ] Validación de env vars
- [ ] Rate limiting en OpenAI

### Supabase
- [ ] Backups configurados (plan pago)
- [ ] RLS habilitado (mejor práctica)
- [ ] Permisos de anon key limitados (lectura)
- [ ] Monitoreo de acceso

### OpenAI
- [ ] API key NO en repositorio
- [ ] Alertas de costo activadas
- [ ] Prompts NO injectables (ok, ya está)
- [ ] Logging de requests sin exponer keys

---

## 🔐 PROCEDIMIENTO DE ROTACIÓN DE CLAVES

Si alguna vez sospechas exposición:

### OpenAI API Key
```bash
1. Ve a https://platform.openai.com/account/api-keys
2. Click "Delete" en la clave actual
3. Click "Create new key"
4. Actualiza .env localmente
5. Redeploy scripts
```

### Supabase Service Role Key
```bash
1. Ve a Supabase Dashboard → Settings → API Keys
2. Revoke la clave actual
3. Crear nueva key
4. Actualizar .env localmente
5. Redeploy evaluador
```

---

## 📞 ALERTAS DE SEGURIDAD

### Configura notificaciones:

**OpenAI:**
- Alerta si mes > $50
- Alerta si requests/día > 1000

**Supabase:**
- Monitorea queries lentAS
- Alerta si storage > 1GB
- Revisar logs de autenticación

**Vercel:**
- Deploy notifications
- Error rate > 1%

---

## ✅ CONCLUSIÓN

**Riesgo General: BAJO-MEDIO**

**Áreas críticas:**
1. ✅ API Keys (.env) — PROTEGIDO
2. ✅ Dashboard — SEGURO
3. ✅ OpenAI — REQUIERE MONITOREO

**Recomendación:** Implementar checklist inmediato (2 horas de trabajo)

---

## 📚 REFERENCIAS

- OWASP Top 10: https://owasp.org/Top10/
- Supabase Security: https://supabase.com/docs/guides/security
- OpenAI Security Best Practices: https://platform.openai.com/docs/guides/production-best-practices
- Vercel Security: https://vercel.com/docs/concepts/projects/security
