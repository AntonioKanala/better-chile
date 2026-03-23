"""
Crawler para la API pública de Ley Chile (BCN) — Better Chile.

Descubre iterativamente IDs de normas escaneando rangos consecutivos
en la API de la BCN, filtra solo leyes, extrae el texto limpio del XML,
y guarda masivamente en Supabase (tabla 'regulaciones').

Estrategias de descubrimiento:
  1. Escaneo por rango de IDs (modo --rango): prueba IDs consecutivos
     y filtra las que sean de tipo "Ley".
  2. Búsqueda por número de ley (modo --desde-ley): itera números de
     ley (ej: 21600..21700) y resuelve el idNorma real.

Uso:
  python scraper_leychile.py --rango 1200000 1201000 --solo-leyes
  python scraper_leychile.py --desde-ley 21680 --cantidad 15
  python scraper_leychile.py --recientes 20
"""

import argparse
import csv
import html
import os
import re
import time
import logging
from xml.etree import ElementTree as ET

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
BCN_XML_URL = "https://www.bcn.cl/leychile/Consulta/obtxml"
BCN_NAV_URL = "https://www.bcn.cl/leychile/navegar"
SUPABASE_TABLE = "regulaciones"  # Tabla unificada
REQUEST_DELAY = 0.3  # segundos entre requests para no sobrecargar BCN


# ---------------------------------------------------------------------------
# Conexión a Supabase
# ---------------------------------------------------------------------------
def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        log.error("Faltan SUPABASE_URL y/o SUPABASE_KEY en .env.")
        return None
    return create_client(url, key)


def ids_ya_guardados(client) -> set:
    """Obtiene los IDs que ya existen en Supabase para evitar re-descargas."""
    if not client:
        return set()
    try:
        resp = client.table(SUPABASE_TABLE).select("id_norma").execute()
        return {r["id_norma"] for r in resp.data}
    except Exception:
        return set()


# ---------------------------------------------------------------------------
# Descarga y parseo de XML
# ---------------------------------------------------------------------------
def descargar_xml(id_norma: str, session: requests.Session) -> str | None:
    """Descarga el XML de una norma. Devuelve None si está vacío o falla."""
    try:
        resp = session.get(
            BCN_XML_URL,
            params={"opt": 7, "idNorma": id_norma},
            timeout=20,
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        if len(resp.text.strip()) < 50:
            return None
        return resp.text
    except requests.RequestException:
        return None


def parsear_norma(xml_str: str) -> dict | None:
    """
    Parsea el XML de la BCN y extrae metadatos + texto limpio.
    Devuelve None si el XML no es parseable.
    """
    # Limpiar entidades HTML no estándar antes de parsear
    xml_limpio = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;', xml_str)
    try:
        root = ET.fromstring(xml_limpio)
    except ET.ParseError:
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            return None

    # Detectar namespace
    ns = ""
    tag = root.tag
    if tag.startswith("{"):
        ns = tag[: tag.index("}") + 1]

    # --- Metadatos ---
    # Tipo de norma (Ley, Decreto, Resolución, etc.)
    tipo_elem = root.find(f".//{ns}Tipo")
    tipo_norma = tipo_elem.text.strip() if tipo_elem is not None and tipo_elem.text else ""

    # Número
    num_elem = root.find(f".//{ns}Numero")
    numero = num_elem.text.strip() if num_elem is not None and num_elem.text else ""

    # Título
    titulo_elem = root.find(f".//{ns}TituloNorma")
    titulo = titulo_elem.text.strip() if titulo_elem is not None and titulo_elem.text else ""

    # Si no hay título explícito, construir uno con tipo + número
    if not titulo and tipo_norma and numero:
        titulo = f"{tipo_norma} {numero}"

    # Fecha de publicación
    fecha = ""
    ident = root.find(f".//{ns}Identificador")
    if ident is not None:
        fecha = ident.get("fechaPublicacion", "")

    # Organismo
    org_elem = root.find(f".//{ns}Organismo")
    organismo = org_elem.text.strip() if org_elem is not None and org_elem.text else ""

    # --- Texto del cuerpo legal (limpio) ---
    texto_limpio = _extraer_texto_cuerpo(root, ns)

    # Descartar normas sin contenido real
    if len(texto_limpio.strip()) < 20:
        return None

    return {
        "tipo_norma": tipo_norma,
        "numero": numero,
        "titulo": titulo,
        "fecha_publicacion": fecha,
        "organismo": organismo,
        "texto_bruto": texto_limpio,
    }


def _extraer_texto_cuerpo(root: ET.Element, ns: str) -> str:
    """
    Extrae el texto legal principal de las secciones del cuerpo:
    Encabezado (preámbulo/vistos/considerando) + EstructurasFuncionales
    (artículos) + Promulgación (firma).

    Evita duplicar metadatos (Materias, Organismos, fuentes).
    """
    secciones = [
        f"{ns}Encabezado",
        f"{ns}EstructurasFuncionales",
        f"{ns}Promulgacion",
    ]

    partes = []
    for tag in secciones:
        for seccion in root.iter(tag):
            _recolectar_texto(seccion, partes)

    # Fallback: si no hay secciones conocidas, extraer todo excepto Metadatos
    if not partes:
        metadatos_tags = {f"{ns}Metadatos", f"{ns}Identificador"}
        for elem in root:
            if elem.tag not in metadatos_tags:
                _recolectar_texto(elem, partes)

    texto = "\n".join(partes)

    # Limpieza final
    texto = html.unescape(texto)                    # &nbsp; &eacute; etc.
    texto = re.sub(r'<[^>]+>', '', texto)            # residuos HTML
    texto = re.sub(r'\n{3,}', '\n\n', texto)        # múltiples saltos
    texto = re.sub(r'[ \t]+', ' ', texto)            # espacios múltiples
    texto = re.sub(r' \n', '\n', texto)              # espacio antes de salto

    return texto.strip()


def _recolectar_texto(elem: ET.Element, partes: list):
    """Recorre recursivamente un elemento y acumula texto."""
    if elem.text and elem.text.strip():
        partes.append(elem.text.strip())
    for child in elem:
        _recolectar_texto(child, partes)
        if child.tail and child.tail.strip():
            partes.append(child.tail.strip())


# ---------------------------------------------------------------------------
# Estrategia 1: Escaneo por rango de IDs
# ---------------------------------------------------------------------------
def crawl_por_rango(
    id_inicio: int,
    id_fin: int,
    solo_leyes: bool = True,
    existentes: set = None,
) -> list[dict]:
    """
    Escanea un rango de IDs consecutivos en la BCN.
    Si solo_leyes=True, filtra únicamente las de tipo 'Ley'.
    """
    existentes = existentes or set()
    resultados = []
    session = requests.Session()
    session.headers.update({"Accept": "application/xml"})

    total = id_fin - id_inicio
    vacios_consecutivos = 0

    log.info("Escaneando rango [%d — %d] (%d IDs)…", id_inicio, id_fin, total)

    for id_norma in range(id_inicio, id_fin):
        str_id = str(id_norma)

        if str_id in existentes:
            log.debug("  %s ya existe en DB, saltando.", str_id)
            continue

        xml = descargar_xml(str_id, session)
        if not xml:
            vacios_consecutivos += 1
            if vacios_consecutivos > 50:
                log.warning("  50+ IDs vacíos consecutivos — probablemente fin del rango.")
                break
            continue

        vacios_consecutivos = 0
        datos = parsear_norma(xml)
        if not datos:
            continue

        if solo_leyes and datos["tipo_norma"].lower() != "ley":
            continue

        log.info(
            "  [%s] %s %s — %s (%d chars)",
            str_id,
            datos["tipo_norma"],
            datos["numero"],
            datos["titulo"][:50],
            len(datos["texto_bruto"]),
        )

        resultados.append({
            "id_norma": str_id,
            "tipo_norma": datos["tipo_norma"],
            "numero": datos.get("numero", ""),
            "titulo": datos["titulo"],
            "fecha_publicacion": datos["fecha_publicacion"],
            "texto_bruto": datos["texto_bruto"],
            "evaluado": False,
        })

        time.sleep(REQUEST_DELAY)

    return resultados


# ---------------------------------------------------------------------------
# Estrategia 2: Iterar por número de ley (21680, 21681, …)
# ---------------------------------------------------------------------------
def crawl_por_numero_ley(
    desde_ley: int,
    cantidad: int = 10,
    existentes: set = None,
) -> list[dict]:
    """
    Busca leyes por su número (ej: Ley 21680) resolviendo el idNorma real.
    Usa el endpoint de navegación de la BCN.
    """
    existentes = existentes or set()
    resultados = []
    session = requests.Session()
    encontradas = 0

    log.info("Buscando %d leyes a partir de Ley %d…", cantidad, desde_ley)

    for num in range(desde_ley, desde_ley + cantidad * 3):
        if encontradas >= cantidad:
            break

        # La BCN redirige /navegar?idLey=XXXXX al idNorma real
        try:
            resp = session.get(
                BCN_NAV_URL,
                params={"idLey": num},
                timeout=15,
                allow_redirects=True,
            )
            # Extraer idNorma de la URL final o del HTML
            id_match = re.search(r'idNorma[=:](\d+)', resp.url + resp.text[:5000])
            if not id_match:
                continue
            id_norma = id_match.group(1)
        except requests.RequestException:
            continue

        if id_norma in existentes:
            continue

        # Descargar XML con el idNorma real
        xml = descargar_xml(id_norma, session)
        if not xml:
            continue

        datos = parsear_norma(xml)
        if not datos:
            continue

        if datos["tipo_norma"].lower() != "ley":
            continue

        log.info(
            "  Ley %d → [%s] %s (%d chars)",
            num, id_norma, datos["titulo"][:50], len(datos["texto_bruto"]),
        )

        resultados.append({
            "id_norma": id_norma,
            "tipo_norma": datos["tipo_norma"],
            "numero": datos.get("numero", ""),
            "titulo": datos["titulo"],
            "fecha_publicacion": datos["fecha_publicacion"],
            "organismo": datos.get("organismo", ""),
            "texto_bruto": datos["texto_bruto"],
            "evaluado": False,
        })
        encontradas += 1
        time.sleep(REQUEST_DELAY)

    return resultados


# ---------------------------------------------------------------------------
# Estrategia 3: Leyes más recientes (rango alto de IDs)
# ---------------------------------------------------------------------------
def crawl_recientes(cantidad: int = 10, existentes: set = None) -> list[dict]:
    """
    Busca las leyes más recientes escaneando desde los IDs más altos
    conocidos hacia abajo.
    """
    existentes = existentes or set()
    resultados = []
    session = requests.Session()

    # Empezar desde un ID alto reciente y buscar hacia abajo
    id_actual = 1210000
    intentos = 0
    max_intentos = cantidad * 80  # ~1 ley cada 40-80 IDs

    log.info("Buscando %d leyes recientes (descendiendo desde ID %d)…", cantidad, id_actual)

    while len(resultados) < cantidad and intentos < max_intentos:
        str_id = str(id_actual)
        id_actual -= 1
        intentos += 1

        if str_id in existentes:
            continue

        xml = descargar_xml(str_id, session)
        if not xml:
            continue

        datos = parsear_norma(xml)
        if not datos:
            continue

        if datos["tipo_norma"].lower() != "ley":
            continue

        log.info(
            "  [%s] Ley %s — %s (%d chars)",
            str_id,
            datos["numero"],
            datos["titulo"][:50],
            len(datos["texto_bruto"]),
        )

        resultados.append({
            "id_norma": str_id,
            "tipo_norma": datos["tipo_norma"],
            "numero": datos.get("numero", ""),
            "titulo": datos["titulo"],
            "fecha_publicacion": datos["fecha_publicacion"],
            "texto_bruto": datos["texto_bruto"],
            "evaluado": False,
        })

        time.sleep(REQUEST_DELAY)

    return resultados


# ---------------------------------------------------------------------------
# Estrategia 4: Descarga desde archivo CSV
# ---------------------------------------------------------------------------
def crawl_desde_csv(
    csv_path: str,
    limite: int = None,
    existentes: set = None,
    client=None,
) -> list[dict]:
    """
    Lee leyes desde un archivo CSV con formato:
    Grupo;Norma;Título;Publicación;Organismo;idNorma;idParte;Url
    Descarga el XML y guarda la categoría (Grupo).

    Si se pasa un client de Supabase, guarda incrementalmente cada 50 leyes
    para no perder progreso en ejecuciones largas.
    """
    existentes = existentes or set()
    resultados = []
    buffer = []
    total_guardados = 0
    BUFFER_SIZE = 50
    session = requests.Session()

    log.info("Leyendo leyes desde CSV: %s (Limite: %s)", csv_path, limite)

    try:
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader)  # skip header

            for row in reader:
                if limite is not None and (total_guardados + len(buffer)) >= limite:
                    log.info("Limite de %d alcanzado.", limite)
                    break
                if len(row) < 6:
                    continue
                # Limpiar BOM de la primera columna
                categoria = row[0].replace('\ufeff', '').strip()

                # idNorma está directamente en row[5]
                id_norma = row[5].strip()
                if not id_norma or not id_norma.isdigit():
                    continue

                if id_norma in existentes:
                    continue

                xml = descargar_xml(id_norma, session)
                if not xml:
                    continue

                datos = parsear_norma(xml)
                if not datos:
                    continue

                log.info(
                    "  [CSV] [%s] %s %s -- Cat: %s (%d chars)",
                    id_norma,
                    datos["tipo_norma"],
                    datos["numero"],
                    categoria[:20],
                    len(datos["texto_bruto"]),
                )

                registro = {
                    "id_norma": id_norma,
                    "tipo_norma": datos["tipo_norma"],
                    "numero": datos.get("numero", ""),
                    "titulo": datos["titulo"],
                    "fecha_publicacion": datos["fecha_publicacion"],
                    "organismo": datos.get("organismo", ""),
                    "categoria": categoria,
                    "texto_bruto": datos["texto_bruto"],
                    "evaluado": False,
                }
                buffer.append(registro)
                resultados.append(registro)

                # Track for deduplication within same run
                existentes.add(id_norma)

                # Incremental save every BUFFER_SIZE laws
                if client and len(buffer) >= BUFFER_SIZE:
                    guardados = guardar_masivo(client, buffer)
                    total_guardados += guardados
                    log.info(
                        "  >> Guardado incremental: %d en este lote, %d total acumulado.",
                        guardados, total_guardados,
                    )
                    buffer = []

                time.sleep(REQUEST_DELAY)

    except Exception as e:
        log.error("Error procesando CSV: %s", e)

    # Guardar el último buffer parcial
    if client and buffer:
        guardados = guardar_masivo(client, buffer)
        total_guardados += guardados
        log.info(
            "  >> Guardado final: %d en ultimo lote, %d total acumulado.",
            guardados, total_guardados,
        )

    return resultados


# ---------------------------------------------------------------------------
# Guardado masivo en Supabase
# ---------------------------------------------------------------------------
def guardar_masivo(client, registros: list[dict]):
    """Inserta registros en lotes para evitar timeouts."""
    if not client:
        log.warning("Sin conexión a Supabase. Mostrando resultados en consola:")
        for r in registros:
            log.info(
                "  [%s] %s | %s | %d chars",
                r["id_norma"], r["titulo"][:60],
                r.get("fecha_publicacion", ""), len(r.get("texto_bruto", "")),
            )
        return 0

    BATCH_SIZE = 20
    guardados = 0

    for i in range(0, len(registros), BATCH_SIZE):
        lote = registros[i : i + BATCH_SIZE]
        try:
            resp = (
                client.table(SUPABASE_TABLE)
                .upsert(lote, on_conflict="id_norma")
                .execute()
            )
            guardados += len(resp.data)
            log.info(
                "  Lote %d/%d guardado: %d registros.",
                i // BATCH_SIZE + 1,
                (len(registros) - 1) // BATCH_SIZE + 1,
                len(resp.data),
            )
        except Exception as e:
            log.error("  Error guardando lote: %s", e)

    return guardados


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Crawler de Ley Chile — Better Chile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scraper_leychile.py --rango 1200000 1201000
  python scraper_leychile.py --desde-ley 21680 --cantidad 15
  python scraper_leychile.py --recientes 20
  python scraper_leychile.py --desde-csv leyes_por_tema.csv
        """,
    )

    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument(
        "--rango",
        nargs=2,
        type=int,
        metavar=("INICIO", "FIN"),
        help="Escanear rango de IDs de norma [INICIO, FIN)",
    )
    grupo.add_argument(
        "--desde-ley",
        type=int,
        metavar="NUM",
        help="Buscar leyes a partir de este número de ley",
    )
    grupo.add_argument(
        "--recientes",
        type=int,
        metavar="N",
        help="Buscar las N leyes más recientes",
    )
    grupo.add_argument(
        "--desde-csv",
        type=str,
        metavar="FILE",
        help="Descargar leyes extraídas desde un archivo CSV con sus categorías",
    )

    parser.add_argument(
        "--cantidad",
        type=int,
        default=10,
        help="Cantidad de leyes a buscar (para --desde-ley, default: 10)",
    )
    parser.add_argument(
        "--todas",
        action="store_true",
        help="Incluir todo tipo de norma, no solo leyes (para --rango)",
    )

    args = parser.parse_args()

    log.info("=" * 60)
    log.info("CRAWLER LEY CHILE — Better Chile")
    log.info("=" * 60)

    client = get_supabase_client()
    existentes = ids_ya_guardados(client)
    log.info("IDs ya en Supabase: %d", len(existentes))

    # Ejecutar estrategia seleccionada
    if args.rango:
        inicio, fin = args.rango
        registros = crawl_por_rango(
            inicio, fin,
            solo_leyes=not args.todas,
            existentes=existentes,
        )
    elif args.desde_ley is not None:
        registros = crawl_por_numero_ley(
            args.desde_ley,
            cantidad=args.cantidad,
            existentes=existentes,
        )
    elif args.recientes:
        registros = crawl_recientes(
            cantidad=args.recientes,
            existentes=existentes,
        )
    elif args.desde_csv:
        # CSV mode uses incremental saving (every 50 laws)
        registros = crawl_desde_csv(
            csv_path=args.desde_csv,
            limite=args.cantidad,
            existentes=existentes,
            client=client,
        )
        # Already saved incrementally, just report
        log.info("=" * 60)
        log.info("COMPLETADO -- %d normas procesadas desde CSV.", len(registros))
        log.info("=" * 60)
        return
    else:
        registros = []

    if not registros:
        log.warning("No se encontraron normas nuevas.")
        return

    log.info("Total normas extraidas: %d", len(registros))

    # Guardar en Supabase
    guardados = guardar_masivo(client, registros)
    log.info("=" * 60)
    log.info("COMPLETADO -- %d normas guardadas en Supabase.", guardados)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
