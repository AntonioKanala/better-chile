"""
Analizar reformas sugeridas — Better Chile

Lee todas las normas con veredicto "modify" y genera un reporte
con los cambios específicos recomendados, agrupados por:
- Categoría de reforma (desregulación, simplificación, modernización)
- Área de impacto (económica, administrativa, fiscal, etc.)
- Prioridad (1-10)
"""

import os
import sys
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("Faltan SUPABASE_URL y/o SUPABASE_KEY en .env")
        sys.exit(1)
    return create_client(url, key)


def obtener_normas_modify(client, limit=None):
    """Trae todas (o N) normas con veredicto='modify', ordenadas por prioridad."""
    query = (
        client.table("regulaciones")
        .select(
            "id_norma, titulo, categoria, verdict, prioridad, "
            "legislative_action, negative_effects, categoria_reforma, "
            "impacto_economico, complejidad_burocracia, reason"
        )
        .eq("verdict", "modify")
        .order("prioridad", desc=True)
    )

    if limit:
        query = query.limit(limit)

    resp = query.execute()
    return resp.data or []


def agrupar_por_categoria(normas):
    """Agrupa normas por categoría de reforma."""
    grupos = defaultdict(list)
    for norma in normas:
        cat = norma.get("categoria_reforma") or "sin_clasificar"
        grupos[cat].append(norma)
    return dict(sorted(grupos.items()))


def agrupar_por_impacto(normas):
    """Agrupa normas por tipo de impacto económico."""
    grupos = defaultdict(list)
    for norma in normas:
        imp = norma.get("impacto_economico") or "desconocido"
        grupos[imp].append(norma)
    # Sort with custom order to handle string comparison
    order = {"alto": 0, "medio": 1, "bajo": 2, "desconocido": 3}
    return dict(sorted(grupos.items(), key=lambda x: order.get(x[0], 4)))


def generar_reporte_reformas(normas):
    """Genera un reporte detallado de reformas sugeridas."""

    print("=" * 80)
    print("ANALISIS DE REFORMAS LEGISLATIVAS — MEJOR CHILE")
    print(f"Total normas a modificar: {len(normas)}")
    print("=" * 80)

    # Por categoría de reforma
    print("\n" + "=" * 80)
    print("1. POR CATEGORIA DE REFORMA")
    print("=" * 80)

    por_categoria = agrupar_por_categoria(normas)

    for categoria, items in por_categoria.items():
        titulo_cat = {
            "desregulacion": "DESREGULACION - Eliminar restricciones",
            "simplificacion": "SIMPLIFICACION - Reducir tramites",
            "modernizacion": "MODERNIZACION - Actualizar tecnologia/procesos",
            "mantener": "MANTENER - Reformas menores"
        }.get(categoria, categoria.upper())

        print(f"\n[{titulo_cat}] — {len(items)} normas")
        print("-" * 80)

        # Top 5 por prioridad en esta categoría
        top = sorted(items, key=lambda x: x.get("prioridad") or 0, reverse=True)[:5]
        for i, norma in enumerate(top, 1):
            print(f"\n  {i}. [{norma['id_norma']}] {norma['titulo'][:70]}")
            print(f"     Prioridad: {norma.get('prioridad', '?')}/10")
            print(f"     Impacto economico: {norma.get('impacto_economico', '?')}")
            print(f"     Accion: {norma.get('legislative_action', 'Sin especificar')[:100]}")
            if norma.get('negative_effects') and norma['negative_effects'] != 'Ninguno':
                print(f"     Efectos negativos: {norma['negative_effects'][:80]}")

    # Por impacto económico
    print("\n" + "=" * 80)
    print("2. ANALISIS POR IMPACTO ECONOMICO")
    print("=" * 80)

    por_impacto = agrupar_por_impacto(normas)

    for impacto, items in por_impacto.items():
        print(f"\n[{impacto.upper()}] — {len(items)} normas")
        print("-" * 80)

        # Promedio de prioridad
        prio_promedio = sum(n.get('prioridad') or 5 for n in items) / len(items)
        print(f"  Prioridad promedio: {prio_promedio:.1f}/10")

        # Top áreas de impacto
        areas = defaultdict(int)
        for norma in items:
            for area in norma.get('impact_areas', []):
                areas[area] += 1

        if areas:
            print(f"  Areas afectadas (top 3):")
            for area, count in sorted(areas.items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"    - {area}: {count} normas")

    # Top 10 reformas urgentes (prioridad >= 8)
    print("\n" + "=" * 80)
    print("3. TOP 10 REFORMAS URGENTES (Prioridad >= 8)")
    print("=" * 80)

    urgentes = [n for n in normas if (n.get('prioridad') or 0) >= 8]
    urgentes_sorted = sorted(urgentes, key=lambda x: x.get('prioridad') or 0, reverse=True)

    if urgentes_sorted:
        for i, norma in enumerate(urgentes_sorted[:10], 1):
            print(f"\n  {i}. [{norma['id_norma']}] {norma['titulo'][:60]}")
            print(f"     [{norma.get('categoria_reforma', '?').upper()}] P{norma.get('prioridad', '?')}")
            print(f"     ACCION: {norma.get('legislative_action', 'Sin especificar')}")
    else:
        print("\n  (Sin normas con prioridad >= 8)")

    # Resumen estadístico
    print("\n" + "=" * 80)
    print("4. RESUMEN ESTADISTICO")
    print("=" * 80)

    compl_alta = len([n for n in normas if n.get('complejidad_burocracia') == 'alta'])
    compl_media = len([n for n in normas if n.get('complejidad_burocracia') == 'media'])
    compl_baja = len([n for n in normas if n.get('complejidad_burocracia') == 'baja'])

    impacto_alto = len([n for n in normas if n.get('impacto_economico') == 'alto'])
    impacto_medio = len([n for n in normas if n.get('impacto_economico') == 'medio'])
    impacto_bajo = len([n for n in normas if n.get('impacto_economico') == 'bajo'])

    print(f"\nComplejidad burocrática:")
    print(f"  Alta:  {compl_alta:3} ({100*compl_alta//len(normas)}%)")
    print(f"  Media: {compl_media:3} ({100*compl_media//len(normas)}%)")
    print(f"  Baja:  {compl_baja:3} ({100*compl_baja//len(normas)}%)")

    print(f"\nImpacto económico:")
    print(f"  Alto:  {impacto_alto:3} ({100*impacto_alto//len(normas)}%)")
    print(f"  Medio: {impacto_medio:3} ({100*impacto_medio//len(normas)}%)")
    print(f"  Bajo:  {impacto_bajo:3} ({100*impacto_bajo//len(normas)}%)")

    print("\n" + "=" * 80)


def exportar_reformas_csv(normas, filename="reformas_sugeridas.csv"):
    """Exporta las reformas a un CSV para análisis posterior."""
    import csv

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'id_norma', 'titulo', 'categoria', 'categoria_reforma',
            'prioridad', 'impacto_economico', 'complejidad_burocracia',
            'legislative_action', 'negative_effects', 'reason'
        ])
        writer.writeheader()

        for norma in normas:
            writer.writerow({
                'id_norma': norma.get('id_norma'),
                'titulo': norma.get('titulo', '')[:100],
                'categoria': norma.get('categoria', ''),
                'categoria_reforma': norma.get('categoria_reforma', ''),
                'prioridad': norma.get('prioridad', ''),
                'impacto_economico': norma.get('impacto_economico', ''),
                'complejidad_burocracia': norma.get('complejidad_burocracia', ''),
                'legislative_action': norma.get('legislative_action', '')[:200],
                'negative_effects': norma.get('negative_effects', '')[:200],
                'reason': norma.get('reason', '')[:200]
            })

    print(f"\nReformas exportadas a: {filename}")


if __name__ == "__main__":
    print("Obteniendo normas para modificar...")

    sb = get_supabase_client()
    normas = obtener_normas_modify(sb)

    if not normas:
        print("No hay normas con veredicto 'modify' aun.")
        sys.exit(0)

    print(f"Obtenidas {len(normas)} normas para analizar.\n")

    # Mostrar reporte
    generar_reporte_reformas(normas)

    # Exportar CSV
    exportar_reformas_csv(normas)
