# Better Chile - Security Setup Guide

**Completar esto ANTES de cualquier cambio de código.**

---

## 🔐 CONFIGURACIÓN DE SEGURIDAD (5 minutos)

### Paso 1: Verificar `.gitignore`

```bash
cd "c:\Users\anton\Documents\Antigravity\Better Chile"
cat .gitignore | grep "\.env"
# Debe mostrar: .env
```

✅ **Estado:** `.gitignore` creado con protección `.env`

---

### Paso 2: Verificar que `.env` NO está en Git

```bash
git status | grep .env
# No debe mostrar nada (.env no está tracked)

git log --name-status --pretty="" -- .env
# No debe mostrar nada (nunca fue committed)
```

✅ **Estado:** `.env` no está en repositorio

---

### Paso 3: Crear `.env.local` (solo local, nunca commit)

```bash
# Root directory
cp .env.example .env
# EDITA .env con tus valores reales

# Dashboard directory
cd dashboard
cp .env.example .env.local
# EDITA .env.local con tus valores reales
```

⚠️ **CRÍTICO:** Nunca hagas `git add .env` o `git add .env.local`

---

### Paso 4: Verificar API Keys están protegidas

```bash
# Verificar que .env NO está en Git
git ls-files | grep "\.env"
# No debe mostrar nada

# Verificar que está en .gitignore
grep "\.env" .gitignore
# Debe mostrar: .env
```

✅ **Status:** Protegido

---

## 🛡️ BUENAS PRÁCTICAS

### 1. Nunca hagas esto:

```bash
# ❌ NUNCA - Expondrá tus claves
git add .env
git commit -m "Add environment"

# ❌ NUNCA - Pondrá claves en historial
git push origin main

# ❌ NUNCA - Loguees claves
console.log(OPENAI_API_KEY)
print(f"API Key: {api_key}")
```

### 2. Siempre haz esto:

```bash
# ✅ SIEMPRE - Mantén .env local
.env  # En .gitignore

# ✅ SIEMPRE - Usa .env.example como template
git add .env.example

# ✅ SIEMPRE - Documenta variables
# Ver .env.example para lista completa

# ✅ SIEMPRE - Log sin exponer claves
log.info(f"Using API key: ...{api_key[-10:]}")  # Solo últimos 10 chars
```

---

## 🔄 ROTACIÓN DE CLAVES (si alguna se expone)

### OpenAI API Key

```bash
# 1. Genera nueva clave en https://platform.openai.com/account/api-keys
# 2. Click "Delete" en clave antigua
# 3. Click "Create new key"
# 4. Copia nueva clave

# 5. Actualiza .env
nano .env
# OPENAI_API_KEY=sk-new_key_here

# 6. Redeploy evaluador
python evaluador_profundo.py

# 7. Verifica en logs que nueva clave funciona
tail -f /tmp/eval_profundo.log
```

### Supabase Service Role Key

```bash
# 1. Ve a https://app.supabase.com → Settings → API Keys
# 2. Click "Revoke" en clave antigua
# 3. Click "Create new secret key"
# 4. Copia nueva clave

# 5. Actualiza .env
nano .env
# SUPABASE_KEY=new_key_here

# 6. Redeploy scripts
python evaluador_profundo.py

# 7. Confirma acceso a base de datos
python -c "from supabase import create_client; ..."
```

---

## 📋 CHECKLIST ANTES DE PRODUCCIÓN

- [ ] `.env` NO está en Git (`git ls-files | grep .env` = nada)
- [ ] `.env.example` está en Git (template sin valores)
- [ ] `.gitignore` incluye `.env`
- [ ] Python scripts validan env vars antes de ejecutar
- [ ] Dashboard usa ANON key (lectura), no service role key
- [ ] OpenAI API key rotada si alguna vez fue expuesta
- [ ] Supabase service role key NO está en código frontend
- [ ] Logging NO expone claves completas
- [ ] `.vercel` directory NO está en Git

---

## 🚨 EMERGENCIAS: Si crees que una clave fue expuesta

### Inmediatamente:

1. **OpenAI API Key expuesta:**
```bash
# Revoke en https://platform.openai.com/account/api-keys
# Crea nueva clave
# Actualiza .env localmente
# Redeploy evaluador
# Monitorea costos por actividad sospechosa
```

2. **Supabase Key expuesta:**
```bash
# Revoke en https://app.supabase.com → Settings → API Keys
# Crea nueva clave
# Actualiza .env localmente
# Redeploy scripts
# Verifica logs de acceso por cambios sospechosos
```

3. **Ambas expuestas:**
```bash
# Repite ambos pasos arriba
# Cambia contraseña Supabase cuenta
# Cambiar contraseña OpenAI cuenta
# Revisar historial de facturas
```

---

## 📞 REFERENCIAS RÁPIDAS

| Servicio | Dashboard | Claves |
|----------|-----------|--------|
| **OpenAI** | https://platform.openai.com/account | API Keys |
| **Supabase** | https://app.supabase.com | Settings → API Keys |
| **Vercel** | https://vercel.com/dashboard | Settings → Env Vars |
| **GitHub** | https://github.com/settings/security | Check commit history |

---

## ✅ VERIFICACIÓN FINAL

```bash
# Ejecutar esto antes de cualquier deploy
./scripts/security-check.sh  # Ver abajo

# O manualmente:
echo "1. Verificando .env..."
[[ $(git ls-files | grep .env | wc -l) -eq 0 ]] && echo "✓ .env not in Git" || echo "✗ ERROR: .env is in Git!"

echo "2. Verificando .gitignore..."
grep -q "\.env" .gitignore && echo "✓ .env in .gitignore" || echo "✗ ERROR: .env NOT in .gitignore"

echo "3. Verificando .env.example existe..."
[[ -f .env.example ]] && echo "✓ .env.example exists" || echo "✗ ERROR: .env.example missing"

echo "4. Verificando que .env NO fue committeado antes..."
[[ $(git log --name-status --pretty="" -- .env | wc -l) -eq 0 ]] && echo "✓ .env never committed" || echo "⚠ WARNING: .env was committed!"
```

---

**Última revisión:** 23 de Marzo de 2026
**Status:** ✅ IMPLEMENTADO

Si tienes dudas sobre seguridad, revisa `SECURITY_REVIEW.md`
