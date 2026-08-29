#!/usr/bin/env python3
"""render_post.py — compone la imagen del dia a partir de posts.yaml.

Se compone en HTML y se rasteriza con Chrome sin ventana. Es el mismo patron
que make_carrusel.py en THIRDEYE y funciona: el texto fluye y se mide solo, y
ajustar el diseno es tocar CSS en vez de recalcular coordenadas a mano.

Uso:
  py -3 render_post.py                      # la fila de hoy
  py -3 render_post.py --fecha 2026-08-16
  py -3 render_post.py --fecha 2026-08-16 --salida prueba.jpg
"""
import argparse
import base64
import html as html_mod
import io
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageOps

from finca_comun import RAIZ, cargar_env, fila_de, hoy, log, morir

def _buscar_chrome():
    """Resuelve el navegador segun donde se corra.

    En Windows es el Chrome instalado; en los runners de GitHub Actions es
    chromium/google-chrome en el PATH. Se busca en vez de fijarlo para que el
    mismo script sirva en los dos sitios sin ramificar el codigo.
    """
    import shutil
    if os.environ.get("CHROME_BIN"):
        return os.environ["CHROME_BIN"]
    for c in ("chromium-browser", "chromium", "google-chrome", "google-chrome-stable"):
        r = shutil.which(c)
        if r:
            return r
    return r"C:\Program Files\Google\Chrome\Application\chrome.exe"


CHROME = _buscar_chrome()
LOGO = os.path.join(RAIZ, "LOGO", "WHITE LOGO - No background.png")
PLANTILLAS = os.path.join(RAIZ, "plantillas")
W, H = 1080, 1350

# `foco` en posts.yaml -> background-position de CSS.
FOCOS = {
    "centro": "center center",
    "arriba": "center top",
    "abajo": "center bottom",
    "izquierda": "left center",
    "derecha": "right center",
}


def foto_b64(ruta, ancho=1500):
    """Carga la foto, corrige la rotacion por EXIF y la reduce.

    Siete fotos de FUTURAS SEMANAS/IMAGENES estan guardadas giradas 90 grados
    (sensor en vertical sobre contenido horizontal). Sin exif_transpose salen
    acostadas y no hay forma de notarlo hasta ver el post publicado.

    Se reduce antes de incrustar: una foto de 4000px en base64 dentro del HTML
    hace que Chrome tarde de mas sin ganar nada, porque el destino son 1080px.
    """
    if not os.path.exists(ruta):
        morir(f"la foto no existe: {ruta}")
    im = Image.open(ruta)
    im = ImageOps.exif_transpose(im).convert("RGB")
    if im.width > ancho:
        im = im.resize((ancho, int(im.height * ancho / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def logo_b64(umbral=60):
    """Recorta el logo a su TRAZO, no a su glow.

    El PNG trae un resplandor horneado que llega a los bordes del lienzo: el
    bbox con alfa>0 da 1024x1515, o sea el archivo entero, y recortar por ahi
    no recorta nada. El trazo real mide 554x486 — el 46% del ancho y el 68% del
    alto eran halo transparente, que es lo que se veia como hueco vacio.

    Umbralizar el alfa antes de medir descarta el halo. El recorte es estable
    con cualquier umbral entre 20 y 250; 60 queda comodo entre ambos extremos.

    El glow que sobrevive DENTRO del recorte se conserva a proposito: pegado al
    trazo hace de sombra y ayuda a leer el logo sobre foto clara.
    """
    im = Image.open(LOGO).convert("RGBA")
    bbox = im.split()[3].point(lambda v: 255 if v > umbral else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def construir_html(fila):
    with open(os.path.join(PLANTILLAS, "base.css"), encoding="utf-8") as fh:
        css = fh.read()
    with open(os.path.join(PLANTILLAS, "full.html"), encoding="utf-8") as fh:
        plantilla = fh.read()

    # La fuente viaja empotrada en el HTML, no se pide al sistema.
    #
    # El 2026-08-29 el primer post salio con letra fina: el CSS pedia 'Arial
    # Black', que existe en Windows pero NO en los runners de Ubuntu, asi que
    # Chrome cayo a la sans por defecto en peso normal. Con la fuente dentro
    # del HTML el render es identico en las dos maquinas.
    with open(os.path.join(PLANTILLAS, "fuentes", "ArchivoBlack.ttf"), "rb") as fh:
        fuente_b64 = base64.b64encode(fh.read()).decode()

    foco = FOCOS.get(str(fila.get("foco", "centro")).lower())
    if foco is None:
        morir(f"foco desconocido: {fila.get('foco')!r}. "
              f"Validos: {', '.join(FOCOS)}")

    titulo = str(fila.get("titulo", "")).strip()
    if not titulo:
        morir("la fila no tiene titulo")
    # El salto de linea lo decide la persona en el YAML, no un algoritmo: en los
    # posts reales el corte esta elegido (TOMATE UN / RESPIRO) y partirlo
    # automaticamente lo rompe.
    titulo = "<br>".join(html_mod.escape(l.strip())
                         for l in titulo.splitlines() if l.strip())

    foto = fila.get("foto")
    if not foto:
        morir("la fila no tiene foto")
    ruta_foto = foto if os.path.isabs(foto) else os.path.join(RAIZ, foto)

    return (plantilla
            .replace("{{CSS}}", css)
            .replace("{{FOTO}}", foto_b64(ruta_foto))
            .replace("{{LOGO}}", logo_b64())
            .replace("{{FOCO}}", foco)
            .replace("{{TITULO}}", titulo)
            .replace("{{FUENTE}}", fuente_b64))


def rasterizar(html, salida):
    tmp_dir = os.path.join(RAIZ, "salidas", "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_html = os.path.join(tmp_dir, "post.html")
    tmp_png = os.path.join(tmp_dir, "post.png")
    for f in (tmp_png,):
        if os.path.exists(f):
            os.remove(f)

    with open(tmp_html, "w", encoding="utf-8") as fh:
        fh.write(html)

    if not (os.path.exists(CHROME) or shutil.which(CHROME)):
        morir(f"no se encuentra Chrome en {CHROME}")

    subprocess.run([
        CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", f"--window-size={W},{H}",
        f"--screenshot={tmp_png}",
        f"file:///{tmp_html.replace(os.sep, '/')}",
    ], capture_output=True, timeout=180)

    if not os.path.exists(tmp_png):
        morir("Chrome no genero la captura")

    os.makedirs(os.path.dirname(salida), exist_ok=True)
    # Instagram exige JPEG y admite hasta 8 MB. A 1080x1350 con q92 son ~400 KB.
    Image.open(tmp_png).convert("RGB").save(salida, "JPEG", quality=92)
    os.remove(tmp_png)
    os.remove(tmp_html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", default=None, help="AAAA-MM-DD (por defecto hoy)")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args()
    cargar_env()

    fecha = a.fecha or hoy()
    fila = fila_de(fecha)
    if fila is None:
        morir(f"no hay fila en posts.yaml para {fecha}")

    salida = a.salida or os.path.join(RAIZ, "salidas", fecha, f"{fecha}.jpg")
    rasterizar(construir_html(fila), salida)

    kb = os.path.getsize(salida) / 1024
    if kb > 8000:
        morir(f"el JPEG pesa {kb/1024:.1f} MB y el limite de Instagram son 8 MB")
    log(f"renderizado: {salida}  ({kb:,.0f} KB)")
    print(salida)


if __name__ == "__main__":
    main()
