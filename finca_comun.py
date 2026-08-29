"""Piezas compartidas por el pipeline de @fincaelguamito.

Vive aparte para que cargar el .env, registrar el estado y ocultar el token no
esten copiados en cinco sitios: si el ocultado del token se rompe en una copia
y no en las otras, el fallo es silencioso y caro.
"""
import datetime
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
MARCA = os.path.join(RAIZ, "finca_pendiente.txt")
COLA = os.path.join(RAIZ, "posts.yaml")


def cargar_env():
    """Lee .env sin dependencias externas. No pisa variables ya definidas."""
    ruta = os.path.join(RAIZ, ".env")
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def log(msg):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def limpiar(texto):
    """Sustituye el token en cualquier texto antes de imprimirlo.

    Las respuestas de error de la Graph API pueden devolver el token dentro del
    mensaje. Sin esto acabaria en los logs de Task Scheduler, que no estan
    protegidos.
    """
    t = os.environ.get("FB_PAGE_TOKEN", "").strip()
    texto = str(texto)
    return texto.replace(t, "<TOKEN-OCULTO>") if t else texto


ESTADO = os.path.join(RAIZ, "salidas", "estado.log")


def registrar(nivel, texto):
    """Deja constancia en salidas/estado.log.

    Decidido el 2026-08-14: no se envia ningun aviso. Sin avisos y sin revision
    diaria, este fichero es lo UNICO que hace visible un fallo — el pipeline
    puede romperse un martes y la cuenta quedarse muda hasta que alguien lo
    note a ojo. Por eso es una linea por evento, legible de un vistazo, y no
    ruido mezclado con el log de ejecucion.

    Se consulta con: py -3 finca_estado.py
    """
    try:
        os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
        marca = datetime.datetime.now().isoformat(timespec="seconds")
        with open(ESTADO, "a", encoding="utf-8") as fh:
            fh.write(f"{marca}\t{nivel}\t{limpiar(texto)}\n")
    except Exception as e:
        # Registrar no puede tumbar una publicacion que por lo demas iba bien.
        log(f"(no se pudo escribir el estado: {e})")


def morir(mensaje):
    """Registra y para. Nunca reintenta ni deja estado a medias."""
    log(f"ERROR: {mensaje}")
    registrar("ERROR", mensaje)
    sys.exit(1)


def leer_cola():
    import yaml

    if not os.path.exists(COLA):
        return None
    with open(COLA, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def fila_de(fecha):
    """Devuelve la fila de posts.yaml para esa fecha, o None.

    La cadencia NO vive en un calculo aparte: una fecha esta en la cola o no
    esta. Una regla de cadencia paralela podria discrepar de la cola y publicar
    un dia que no toca, o callarse uno que si.
    """
    cola = leer_cola()
    if cola is None:
        return None
    objetivo = str(fecha)
    for fila in cola:
        if str(fila.get("fecha")) == objetivo:
            return fila
    return None


def hoy():
    return datetime.date.today().isoformat()


def url_publica(fecha):
    base = os.environ.get("FINCA_PAGES_BASE_URL", "").strip().rstrip("/")
    if not base:
        morir("falta FINCA_PAGES_BASE_URL en .env")
    return f"{base}/img/{fecha}.jpg"
