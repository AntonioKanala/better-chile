"""
Evaluador Profundo — Better Chile

Segunda pasada de evaluación usando GPT-4o para análisis de nivel think tank.
Genera propuestas legislativas específicas, citas textuales, análisis comparado.

Para las ~500 normas críticas (prioridad >= 6 o sector laboral):
- Identifica artículos problemáticos específicos
- Cita texto legal literal
- Propone reforma legislativa concreta
- Análisis comparado con otros países
- Estimación de impacto económico
"""

import os
import sys
import json
import time
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI

load_dotenv()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configuration
MODELO = "gpt-4o"
MAX_TEXTO_CHARS = 40_000  # Slightly more than superficial pass for GPT-4o
BATCH_SIZE = 5  # Process 5 at a time to avoid rate limits
DELAY_BETWEEN_REQUESTS = 3  # seconds

# Prompts
SYSTEM_PROMPT_PROFUNDO = """Eres un analista legal especializado en regulación económica, con perspectiva austriaca (libertad económica, desconfianza de planificación central).

Tu tarea es hacer un análisis PROFUNDO de una norma chilena para un reporte de think tank dirigido a gobierno.

INSTRUCCIONES CRÍTICAS:
1. CITA ESPECÍFICA: Identifica los artículos específicos problemáticos. Di exactamente qué artículos y por qué.
2. PROPUESTA LEGISLATIVA: Redacta texto legal concreto (Artículo 1°: Deroganse los artículos..., Artículo 2°: Modifíquese...). NO genérico.
3. IMPACTO ECONÓMICO: Estima concretamente (número de empresas afectadas, costo anual USD, ahorro potencial)
4. COMPARATIVA INTERNACIONAL: Cómo otros países (NZ, Estonia, Singapur, Costa Rica) resuelven el problema
5. JURISPRUDENCIA: Si hay Sentencias de Tribunales Constitucionales relevantes, menciónala

TONO: Profesional, académico, citable en documentos de gobierno.
LONGITUD: Completa, 1500-2000 palabras. No resumido.
"""

USER_PROMPT_TEMPLATE_PROFUNDO = """NORMA A EVALUAR:
Ley/Decreto: {tipo_norma} N° {id_norma}
Título: {titulo}
Fecha: {fecha}

CONTEXTO DE PRIMERA PASADA:
- Veredicto: {verdict}
- Prioridad: {prioridad}/10
- Impacto Económico: {impacto_economico}
- Complejidad Burocrática: {complejidad_burocracia}
- Categoría de Reforma: {categoria_reforma}

ANÁLISIS SUPERFICIAL PREVIO:
{resumen}

TEXTO COMPLETO DE LA NORMA:
{texto_norma}

---

TAREA:
Proporciona un análisis PROFUNDO y ESPECÍFICO que incluya:

1. **ARTÍCULOS PROBLEMÁTICOS** (max 3-5 más críticos)
   Formato: "Art. X: [cita textual de 1-2 líneas] — Problema: [explicación específica]"

2. **PROPUESTA LEGISLATIVA CONCRETA**
   Redacta como proyecto de ley real. Ejemplo:
   "Artículo 1°: Deroganse los artículos 5, 7 y 12 de la Ley N° 19.XXX.
    Artículo 2°: Modifíquese el artículo 15 del mismo cuerpo legal para cambiar [cambio específico]."

3. **IMPACTO ECONÓMICO ESTIMADO**
   - Número de empresas/personas afectadas
   - Costo anual de cumplimiento (USD estimado)
   - Ahorro potencial si se implementa reforma
   - Sectores más impactados

4. **ANÁLISIS COMPARADO**
   ¿Cómo resuelven esto en:
   - Nueva Zelanda
   - Estonia
   - Singapur
   - Costa Rica
   Explica brevemente el mecanismo más efectivo.

5. **JURISPRUDENCIA RELEVANTE**
   ¿Hay sentencias de TC/CS que aborden este tema? ¿Qué dice?

6. **RECOMENDACIONES PRÁCTICAS PARA IMPLEMENTACIÓN**
   Si esto fuera parte de una "Ley Bases", ¿en qué orden debería implementarse?

---

IMPORTANTE:
- SÉ ESPECÍFICO. No digas "simplificar" sino "eliminar los 15 pasos del artículo X y mantener solo autorregistro"
- CITA TEXTO. Pega entre comillas el artículo problemático
- CIFRAS. Busca estimar números reales, no solo "impacto alto"
- SIN IDEOLOGÍA PURA. Fundamenta en eficiencia, no solo libertad
"""

def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("ERROR: Faltan SUPABASE_URL y/o SUPABASE_KEY en .env")
        sys.exit(1)
    return create_client(url, key)


def obtener_normas_criticas(client, sector=None, limit=None):
    """
    Obtiene normas críticas para evaluación profunda.

    Criterios:
    - Prioridad >= 6 (o todas si sector especificado)
    - Si sector='laboral': todas las normas en categoría laboral
    - Que no hayan sido evaluadas profundamente aún
    """

    query = (
        client.table("regulaciones")
        .select(
            "id_norma, tipo_norma, titulo, fecha_publicacion, categoria, "
            "verdict, prioridad, summary, texto_bruto, impacto_economico, "
            "complejidad_burocracia, categoria_reforma, evaluacion_profunda"
        )
        .eq("evaluado", True)
        .eq("evaluacion_profunda", False)  # No evaluadas profundamente aún
    )

    if sector == "laboral":
        # Categorías relacionadas con trabajo/empleo
        query = query.in_("categoria", ["Trabajo", "Códigos del Trabajo", "Seguridad Social"])
    else:
        # Prioridad alta
        query = query.gte("prioridad", 6)

    query = query.order("prioridad", desc=True)

    if limit:
        query = query.limit(limit)

    resp = query.execute()
    return resp.data or []


def evaluar_profundo(norma):
    """
    Evalúa una norma con GPT-4o para análisis profundo.
    """

    # Truncar texto si es necesario
    texto = norma.get("texto_bruto", "")
    if len(texto) > MAX_TEXTO_CHARS:
        texto = texto[:MAX_TEXTO_CHARS] + "\n\n[...TEXTO TRUNCADO...]"

    user_prompt = USER_PROMPT_TEMPLATE_PROFUNDO.format(
        tipo_norma=norma.get("tipo_norma", "?"),
        id_norma=norma.get("id_norma", "?"),
        titulo=norma.get("titulo", "?")[:100],
        fecha=norma.get("fecha_publicacion", "?"),
        verdict=norma.get("verdict", "?"),
        prioridad=norma.get("prioridad", "?"),
        impacto_economico=norma.get("impacto_economico", "?"),
        complejidad_burocracia=norma.get("complejidad_burocracia", "?"),
        categoria_reforma=norma.get("categoria_reforma", "?"),
        resumen=norma.get("summary", "Sin resumen"),
        texto_norma=texto
    )

    try:
        response = openai_client.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_PROFUNDO},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )

        analisis_profundo = response.choices[0].message.content
        return analisis_profundo

    except Exception as e:
        print(f"  ERROR evaluando {norma['id_norma']}: {str(e)}")
        return None


def guardar_evaluacion_profunda(client, id_norma, analisis):
    """Guarda la evaluación profunda en la base de datos."""
    try:
        client.table("regulaciones").update({
            "analisis_profundo": analisis,
            "evaluacion_profunda": True
        }).eq("id_norma", id_norma).execute()
        return True
    except Exception as e:
        print(f"  ERROR guardando evaluación de {id_norma}: {str(e)}")
        return False


def run(sector=None, limit=None):
    """Ejecuta la evaluación profunda."""

    print("\n" + "=" * 80)
    print("EVALUADOR PROFUNDO — Better Chile")
    if sector:
        print(f"Sector: {sector.upper()}")
    print("=" * 80 + "\n")

    client = get_supabase_client()

    print("Obteniendo normas críticas para evaluación profunda...")
    normas = obtener_normas_criticas(client, sector=sector, limit=limit)

    if not normas:
        print("No hay normas pendientes de evaluación profunda.")
        return

    print(f"Encontradas {len(normas)} normas para evaluar.")
    print(f"Costo estimado: ~${len(normas) * 0.15:.2f} USD (GPT-4o)")
    print("Iniciando evaluación profunda...")

    procesadas = 0
    exitosas = 0

    for i, norma in enumerate(normas, 1):
        id_norma = norma.get("id_norma")
        titulo = norma.get("titulo", "")[:60]

        print(f"\n[{i}/{len(normas)}] Evaluando [{id_norma}] {titulo}")

        # Evaluar
        analisis = evaluar_profundo(norma)
        if not analisis:
            continue

        # Guardar
        if guardar_evaluacion_profunda(client, id_norma, analisis):
            print(f"  [OK] Guardado exitosamente")
            exitosas += 1

        procesadas += 1

        # Rate limiting
        if i < len(normas):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    print("\n" + "=" * 80)
    print(f"RESUMEN: {exitosas}/{procesadas} evaluaciones profundas guardadas")
    print("=" * 80)


if __name__ == "__main__":
    # Uso: python evaluador_profundo.py [sector] [limit]
    # Ejemplos:
    #   python evaluador_profundo.py              # Top 500 normas prioridad >= 6
    #   python evaluador_profundo.py laboral      # Todas las normas laborales
    #   python evaluador_profundo.py laboral 50   # Top 50 normas laborales

    sector = sys.argv[1] if len(sys.argv) > 1 else None
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

    run(sector=sector, limit=limit)
