#!/usr/bin/env python3
"""publicar_finca.py — publica el post del dia en @fincaelguamito.

Publicar una imagen por la Graph API son DOS llamadas, no una:

  1. POST /{ig}/media          crea el contenedor con image_url y caption
  2. POST /{ig}/media_publish  lo publica

Entre las dos se espera a que el contenedor este FINISHED. En THIRDEYE,
publicar un segundo despues de crearlo devolvio "Media ID is not available
(code 9007)": el contenedor estaba listo al mirarlo despues, pero en ese
instante aun no estaba registrado. Es una carrera, asi que se repetiria siempre.

Uso:
  py -3 publicar_finca.py --pendiente --dry-run
  py -3 publicar_finca.py --pendiente
  py -3 publicar_finca.py --fecha 2026-08-16
"""
import argparse
import datetime
import os
import sys
import time

import requests

from finca_comun import (MARCA, cargar_env, fila_de, hoy, limpiar, log, morir,
                         registrar, url_publica)

VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{VERSION}"


def api(metodo, ruta, **params):
    token = os.environ.get("FB_PAGE_TOKEN", "").strip()
    if not token:
        morir("falta FB_PAGE_TOKEN en .env")
    params["access_token"] = token
    r = getattr(requests, metodo)(f"{GRAPH}/{ruta}", params=params, timeout=90)
    try:
        d = r.json()
    except ValueError:
        raise RuntimeError(f"respuesta no-JSON: {limpiar(r.text[:300])}")
    if "error" in d:
        e = d["error"]
        raise RuntimeError(f"{limpiar(e.get('message'))} (code {e.get('code')})")
    return d


def esperar_contenedor(cid, minutos=5):
    limite = time.time() + minutos * 60
    ultimo = None
    while time.time() < limite:
        d = api("get", cid, fields="status_code,status")
        estado = d.get("status_code")
        if estado != ultimo:
            log(f"  {cid}: {estado}")
            ultimo = estado
        if estado == "FINISHED":
            return True
        if estado in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"el contenedor quedo en {estado}: "
                               f"{limpiar(d.get('status'))}")
        time.sleep(8)
    raise RuntimeError(f"el contenedor no acabo en {minutos} minutos")


def texto_del_post(fila):
    caption = str(fila.get("caption", "")).strip()
    etiquetas = fila.get("hashtags") or []
    if etiquetas:
        caption += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in etiquetas)
    return caption


def leer_marca():
    """Lee la marca y exige que sea de HOY.

    En THIRDEYE, el 2026-08-11 se republico solo el carrusel del dia anterior
    porque la marca vieja seguia ahi, y hubo que borrarlo a mano. Si no es de
    hoy se borra: dejarla puesta repetiria el fallo manana.
    """
    if not os.path.exists(MARCA):
        log("no hay nada pendiente; nada que publicar")
        return None
    escrita = datetime.date.fromtimestamp(os.path.getmtime(MARCA))
    if escrita.isoformat() != hoy():
        log(f"la marca es del {escrita}, no de hoy ({hoy()}); no se publica. "
            f"Se borra para que no lo reintente manana.")
        os.remove(MARCA)
        return None
    with open(MARCA, encoding="utf-8") as fh:
        fecha = fh.read().strip()
    if fecha != hoy():
        log(f"la marca dice {fecha!r} pero hoy es {hoy()}; no se publica")
        os.remove(MARCA)
        return None
    return fecha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", default=None)
    ap.add_argument("--pendiente", action="store_true",
                    help="lee la fecha de finca_pendiente.txt y borra la marca al publicar")
    ap.add_argument("--dry-run", action="store_true",
                    help="crea el contenedor pero NO publica; caduca solo en 24h")
    a = ap.parse_args()
    cargar_env()

    if a.pendiente:
        fecha = leer_marca()
        if fecha is None:
            return
    else:
        fecha = a.fecha or hoy()

    fila = fila_de(fecha)
    if fila is None:
        morir(f"no hay fila en posts.yaml para {fecha}")

    ig = os.environ.get("IG_USER_ID", "").strip()
    if not ig:
        morir("falta IG_USER_ID en .env")

    url = url_publica(fecha)
    caption = texto_del_post(fila)
    log(f"{fecha} | {url} | pie de {len(caption)} caracteres")

    try:
        # Se comprueba que la imagen se pueda descargar ANTES de pedirsela a
        # Instagram: si la URL falla, el contenedor queda en ERROR y hay que
        # empezar de cero.
        h = requests.head(url, timeout=30, allow_redirects=True)
        tipo = (h.headers.get("Content-Type") or "").lower()
        if h.status_code != 200 or not tipo.startswith("image/"):
            raise RuntimeError(f"{url} no es descargable "
                               f"(HTTP {h.status_code}, {tipo or 'sin tipo'})")

        cid = api("post", f"{ig}/media", image_url=url, caption=caption)["id"]
        log(f"contenedor creado: {cid}")
        esperar_contenedor(cid)

        if a.dry_run:
            log("--dry-run: NO se publica. El contenedor caduca solo en 24h")
            return

        media_id = api("post", f"{ig}/media_publish", creation_id=cid)["id"]
        log(f"PUBLICADO: {media_id}")

        if a.pendiente and os.path.exists(MARCA):
            os.remove(MARCA)
            log("marca consumida")

        enlace = ""
        try:
            enlace = api("get", media_id, fields="permalink").get("permalink", "")
            log(enlace)
        except Exception:
            pass
        registrar("OK", f"publicado {fecha} -> {enlace or media_id}")

    except Exception as e:
        log(f"ERROR: {limpiar(e)}")
        registrar("ERROR", f"NO se publico el post del {fecha}: {limpiar(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
