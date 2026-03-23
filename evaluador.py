"""
Evaluador de leyes chilenas — Better Chile.

Lee normas no evaluadas desde Supabase, las envía a GPT-4o (OpenAI)
para análisis desde la perspectiva de Mises, Hayek y Friedman,
y guarda el veredicto estructurado de vuelta en Supabase.
"""

import json
import os
import re
import sys
import logging
import time

from openai import OpenAI, RateLimitError
from dotenv import load_dotenv
from supabase import create_client
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
MODELO_LARGO = "gpt-4o-mini"
MODELO_CORTO = "gpt-4o-mini"
UMBRAL_MINI = 2000  # Textos <= 2000 chars usan modelo mini (mas barato)
MAX_TEXTO_CHARS = 30_000  # Truncar textos largos (ahorra tokens y costos)
SUPABASE_TABLE = "regulaciones"  # Tabla unificada

SYSTEM_PROMPT = """\
Eres un analista de politicas publicas del proyecto "Better Chile", \
con formacion en la Escuela Austriaca de Economia (Ludwig von Mises, \
Friedrich Hayek, Rothbard) y la Escuela de Chicago (Milton Friedman).

Tu mision es evaluar leyes y regulaciones chilenas (leyes, decretos, DFL, \
DL, resoluciones) y determinar su impacto en la libertad economica y las \
instituciones. Debes actuar con el pragmatismo de un legislador reformista, \
evaluando segun estos 6 ejes:

1. LIBERTAD ECONOMICA: Restringe libre empresa, comercio, competencia?
2. BUROCRACIA ESTATAL: Crea tramites, permisos, autorizaciones innecesarias?
3. COSTO FISCAL: Genera gasto publico sin retorno claro?
4. MODERNIZACION: Es obsoleta? Hay tecnologia/mecanismo mejor?
5. DUPLICACION: Se superpone con otras normas vigentes?
6. DERECHOS FUNDAMENTALES: Protege derechos que deben preservarse?

VEREDICTOS POSIBLES:
- "delete": Normas que coartan directamente libertades, imponen controles de \
precios, monopolios estatales sin justificacion, o crean burocracia inutil.
- "modify": Normas con intenciones razonables (ej. seguridad, salud) pero con \
pesima implementacion estatista, asimetrica o que coartan competencia. No se pueden \
simplemente eliminar sin vacio legal, deben ser reformadas.
- "keep": Normas esenciales para el Estado de Derecho, propiedad, contratos, \
seguridad o defensa.

INSTRUCCIONES DE FORMATO:
- Responde UNICAMENTE con un objeto JSON valido, sin texto adicional.
- NO uses bloques de codigo markdown (```).
- El JSON debe tener exactamente esta estructura:

{
  "summary": "Breve resumen neutral de lo que hace la norma (1-2 oraciones).",
  "verdict": "keep | modify | delete",
  "reason": "Justificacion economica/filosofica de tu veredicto (2-3 oraciones).",
  "negative_effects": "Efectos secundarios nocivos (ej. Barreras de entrada a PYMEs). 'Ninguno' si no hay.",
  "legislative_action": "Accion concreta recomendada (ej. 'Derogar arts. 5-12', 'Simplificar permisos a auto-declaracion').",
  "impact_areas": ["Area1", "Area2"],
  "impacto_economico": "alto | medio | bajo",
  "complejidad_burocracia": "alta | media | baja",
  "prioridad": 1-10 (10 = urgente eliminar/reformar),
  "categoria_reforma": "desregulacion | simplificacion | modernizacion | mantener"
}
"""

USER_PROMPT_TEMPLATE = """\
Evalua la siguiente norma chilena:

TIPO: {tipo_norma}
TITULO: {titulo}
FECHA DE PUBLICACION: {fecha}
CATEGORIA TEMATICA: {categoria}

TEXTO COMPLETO:
{texto}
"""


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        log.error("Faltan SUPABASE_URL y/o SUPABASE_KEY en .env.")
        sys.exit(1)
    return create_client(url, key)


def obtener_normas_pendientes(client, limite: int):
    """Trae normas con evaluado=false."""
    resp = (
        client.table(SUPABASE_TABLE)
        .select("id_norma, tipo_norma, titulo, fecha_publicacion, categoria, texto_bruto")
        .eq("evaluado", False)
        .limit(limite)
        .execute()
    )
    return resp.data


def guardar_evaluacion(client, id_norma: str, evaluacion: dict):
    """Actualiza una norma con su evaluacion completa y marca evaluado=true."""
    update_data = {
        "verdict": evaluacion.get("verdict"),
        "summary": evaluacion.get("summary"),
        "reason": evaluacion.get("reason"),
        "negative_effects": evaluacion.get("negative_effects"),
        "legislative_action": evaluacion.get("legislative_action"),
        "impact_areas": evaluacion.get("impact_areas"),
        "impacto_economico": evaluacion.get("impacto_economico"),
        "complejidad_burocracia": evaluacion.get("complejidad_burocracia"),
        "prioridad": evaluacion.get("prioridad"),
        "categoria_reforma": evaluacion.get("categoria_reforma"),
        "evaluado": True,
        "evaluated_at": "now()",
    }
    resp = (
        client.table(SUPABASE_TABLE)
        .update(update_data)
        .eq("id_norma", id_norma)
        .execute()
    )
    return resp.data


# ---------------------------------------------------------------------------
# OpenAI / GPT-4o
# ---------------------------------------------------------------------------
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        log.error("Falta OPENAI_API_KEY en .env.")
        sys.exit(1)
    return OpenAI(api_key=api_key)


@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=2, min=5, max=120),
    stop=stop_after_attempt(5),
    before_sleep=lambda rs: log.warning(
        "  Rate limit — reintentando en %.0f s (intento %d/5)…",
        rs.next_action.sleep, rs.attempt_number,
    ),
)
def evaluar_con_llm(client: OpenAI, norma: dict) -> dict:
    """
    Envia el texto de una norma a GPT-4o y devuelve el JSON de evaluacion.
    Usa GPT-4o-mini para textos cortos (ahorro de costos).
    Incluye retry automatico ante rate limits.
    """
    texto = norma["texto_bruto"]
    if len(texto) > MAX_TEXTO_CHARS:
        log.warning(
            "  Texto de norma %s truncado de %d a %d chars.",
            norma["id_norma"], len(texto), MAX_TEXTO_CHARS,
        )
        texto = texto[:MAX_TEXTO_CHARS] + "\n[... texto truncado ...]"

    modelo = MODELO_CORTO if len(texto) <= UMBRAL_MINI else MODELO_LARGO

    user_msg = USER_PROMPT_TEMPLATE.format(
        tipo_norma=norma.get("tipo_norma", "Ley"),
        titulo=norma.get("titulo", "Sin titulo"),
        fecha=norma.get("fecha_publicacion", "Sin fecha"),
        categoria=norma.get("categoria", "Sin categoria"),
        texto=texto,
    )

    response = client.chat.completions.create(
        model=modelo,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()

    # Intentar parsear JSON directamente
    try:
        resultado = json.loads(raw)
    except json.JSONDecodeError:
        # A veces el modelo envuelve en ```json ... ```
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            resultado = json.loads(match.group())
        else:
            raise ValueError(f"Respuesta no es JSON válido: {raw[:200]}")

    # Validar estructura minima
    for clave in ("summary", "verdict", "reason", "negative_effects", "legislative_action", "impact_areas"):
        if clave not in resultado:
            raise ValueError(f"Falta clave '{clave}' en respuesta: {resultado}")

    if resultado["verdict"] not in ("keep", "modify", "delete"):
        raise ValueError(f"Verdict invalido: {resultado['verdict']}")

    # Asegurar que prioridad sea int
    if "prioridad" in resultado:
        try:
            resultado["prioridad"] = int(resultado["prioridad"])
        except (ValueError, TypeError):
            resultado["prioridad"] = 5

    log.info("  [%s] %s", modelo, norma["id_norma"])
    return resultado


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
BATCH_FETCH_SIZE = 20  # Cuantas normas pedir a Supabase por lote


def run(limite: int = 5):
    log.info("=" * 60)
    log.info("EVALUADOR BETTER CHILE -- Limite: %d normas", limite)
    log.info("Modelos: %s (largo) / %s (corto <= %d chars)",
             MODELO_LARGO, MODELO_CORTO, UMBRAL_MINI)
    log.info("Fetch batch size: %d", BATCH_FETCH_SIZE)
    log.info("=" * 60)

    sb = get_supabase_client()
    llm = get_openai_client()

    evaluadas = 0
    errores = 0

    while evaluadas + errores < limite:
        # Pedir lotes pequenos para evitar timeout de Supabase
        fetch_size = min(BATCH_FETCH_SIZE, limite - evaluadas - errores)
        normas = obtener_normas_pendientes(sb, fetch_size)
        if not normas:
            log.info("No hay mas normas pendientes de evaluar.")
            break

        log.info("Lote: %d normas (acumulado: %d evaluadas, %d errores)",
                 len(normas), evaluadas, errores)

        for norma in normas:
            if evaluadas + errores >= limite:
                break

            id_norma = norma["id_norma"]
            titulo = norma.get("titulo", "")[:80]
            log.info("[%d/%d] Evaluando [%s] %s",
                     evaluadas + errores + 1, limite, id_norma, titulo)

            try:
                evaluacion = evaluar_con_llm(llm, norma)
            except Exception as e:
                log.error("  Error evaluando norma %s: %s", id_norma, e)
                errores += 1
                continue

            log.info(
                "  Veredicto: %s | prio=%s | %s",
                evaluacion["verdict"].upper(),
                evaluacion.get("prioridad", "?"),
                evaluacion["reason"][:80],
            )

            try:
                guardar_evaluacion(sb, id_norma, evaluacion)
                evaluadas += 1
            except Exception as e:
                log.error("  Error guardando evaluacion de %s: %s", id_norma, e)
                errores += 1

            time.sleep(2)

    log.info("=" * 60)
    log.info(
        "COMPLETADO -- %d evaluadas, %d errores.",
        evaluadas, errores,
    )
    log.info("=" * 60)


if __name__ == "__main__":
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run(limite=limite)
