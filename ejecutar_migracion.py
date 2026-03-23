"""
Ejecutar migración SQL en Supabase
"""
import os
import sys
from dotenv import load_dotenv
import psycopg2
import subprocess

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Extraer host de la URL
# Format: https://[project].supabase.co -> [project].supabase.co
if not SUPABASE_URL:
    print("ERROR: SUPABASE_URL no encontrado en .env")
    sys.exit(1)

host = SUPABASE_URL.replace("https://", "").replace("http://", "")

print(f"Conectando a Supabase: {host}")
print("(Asegúrate de que SUPABASE_KEY es el rol service_role para ejecutar DDL)")

# Leer la migración
with open("migrate_deep_eval.sql", "r") as f:
    sql = f.read()

print("\nMigración SQL a ejecutar:")
print("=" * 60)
print(sql)
print("=" * 60)

# Opción 1: Usar psql si está disponible
try:
    import subprocess
    result = subprocess.run(
        ["psql", "-h", host, "-U", "postgres", "-d", "postgres", "-c", sql],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode == 0:
        print("\n✓ Migración ejecutada exitosamente")
        print(result.stdout)
    else:
        print(f"\n✗ Error: {result.stderr}")
        sys.exit(1)
except FileNotFoundError:
    print("\npsql no encontrado. Intenta ejecutar manualmente en Supabase SQL Editor:")
    print("1. Ve a https://app.supabase.com")
    print("2. Tu proyecto → SQL Editor → New Query")
    print("3. Copia y pega el contenido de migrate_deep_eval.sql")
    print("4. Click en RUN")
except Exception as e:
    print(f"\nError: {e}")
    sys.exit(1)
