#!/usr/bin/env python3
"""finca_estado.py — que ha hecho el pipeline ultimamente.

Como no se envia ningun aviso y nadie revisa las piezas antes de publicarlas,
este comando es la forma de enterarse de que algo se rompio. Conviene mirarlo
de vez en cuando: si el ultimo evento es de hace ocho dias, el pipeline lleva
ocho dias sin publicar y nadie se habia enterado.

Uso:
  py -3 finca_estado.py
  py -3 finca_estado.py --lineas 40
"""
import argparse
import datetime
import os

from finca_comun import ESTADO, MARCA, cargar_env, fila_de, hoy, leer_cola


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lineas", type=int, default=15)
    a = ap.parse_args()
    cargar_env()

    print("=== ULTIMOS EVENTOS ===")
    if not os.path.exists(ESTADO):
        print("  (sin registro todavia: el pipeline nunca ha corrido)")
    else:
        with open(ESTADO, encoding="utf-8") as fh:
            lineas = [l.rstrip("\n") for l in fh if l.strip()]
        for l in lineas[-a.lineas:]:
            partes = l.split("\t", 2)
            if len(partes) == 3:
                cuando, nivel, texto = partes
                print(f"  {cuando}  {nivel:6s}  {texto}")
            else:
                print(f"  {l}")

        # Un pipeline que no publica no da errores: simplemente se calla. Por eso
        # lo que importa no es solo si hubo fallos, sino cuanto hace del ultimo
        # evento de cualquier tipo.
        ultimo = lineas[-1].split("\t")[0]
        try:
            dias = (datetime.datetime.now()
                    - datetime.datetime.fromisoformat(ultimo)).days
            if dias >= 3:
                print(f"\n  AVISO: el ultimo evento es de hace {dias} dias.")
        except ValueError:
            pass

    print("\n=== AHORA MISMO ===")
    marca = "no hay" if not os.path.exists(MARCA) else (
        datetime.date.fromtimestamp(os.path.getmtime(MARCA)).isoformat())
    print(f"  marca pendiente: {marca}")
    print(f"  hoy ({hoy()}): {'toca' if fila_de(hoy()) else 'no toca'}")

    cola = leer_cola() or []
    futuras = sorted(str(f.get("fecha")) for f in cola if str(f.get("fecha")) >= hoy())
    print(f"  fechas en la cola desde hoy: {len(futuras)}")
    for f in futuras[:5]:
        print(f"    {f}")
    if not futuras:
        print("    NINGUNA. La cola esta agotada y no se publicara nada mas.")


if __name__ == "__main__":
    main()
