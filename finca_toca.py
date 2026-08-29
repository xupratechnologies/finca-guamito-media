#!/usr/bin/env python3
"""finca_toca.py — ¿toca publicar hoy?

Codigos de salida, pensados para que un .bat encadene sin ambiguedad:

  0  toca: hay fila para hoy en posts.yaml
  1  no toca: no hay fila para hoy. Es lo NORMAL los dias sin post.
     Para en silencio y sin avisar.
  2  no se sabe: posts.yaml no existe o no se puede leer. Avisa y para.
     Publicar a ciegas es peor que no publicar.

La cadencia no se calcula: una fecha esta en la cola o no esta. Una regla de
cadencia paralela (`cada 2 dias desde X`) podria discrepar de la cola y
publicar un dia que no toca, o callarse uno que si. La cola manda.

Uso:
  py -3 finca_toca.py
  py -3 finca_toca.py --fecha 2026-08-16
"""
import argparse
import sys

from finca_comun import COLA, cargar_env, fila_de, hoy, leer_cola, log, registrar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", default=None)
    a = ap.parse_args()
    cargar_env()

    fecha = a.fecha or hoy()

    try:
        cola = leer_cola()
    except Exception as e:
        log(f"posts.yaml no se pudo leer: {e}")
        registrar("ERROR", f"posts.yaml ilegible, no se publica nada: {e}")
        sys.exit(2)

    if cola is None:
        log(f"no existe {COLA}")
        registrar("ERROR", "falta posts.yaml, no se publica nada")
        sys.exit(2)

    fila = fila_de(fecha)
    if fila is None:
        log(f"no hay fila para {fecha}; hoy no toca")
        sys.exit(1)

    log(f"toca: {fecha} | {str(fila.get('titulo','')).splitlines()[0]}")
    sys.exit(0)


if __name__ == "__main__":
    main()
