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


def accesorio_logo(im, cx, cy, r, efecto):
    """Le pone al pato del logo el gorro de la fecha (pedido el 2026-11-18).

    cx, cy, r son el centro y el radio de la cabeza del pato EN ESA imagen: el
    logo blanco de los posts y el verde de la foto de perfil tienen el pato en
    sitios y tamanos distintos, asi que todo se dibuja en unidades de `r`.

    Se dibuja a 4x y se reduce: a 1x los bordes del gorro salen dentados, y en
    el post el logo entero mide 175 px.
    """
    import math
    from PIL import ImageDraw
    efecto = str(efecto or "").lower()
    if efecto not in ("navidad", "anonuevo", "carnaval", "amor"):
        return im
    S = 4
    capa = Image.new("RGBA", (im.width * S, im.height * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)

    def P(x, y):  # unidades de r, relativas a la cabeza -> pixeles a 4x
        return ((cx + x * r) * S, (cy + y * r) * S)

    def bola(x, y, rad, color, borde=None):
        px, py = P(x, y)
        q = rad * r * S
        d.ellipse((px - q, py - q, px + q, py + q), fill=color,
                  outline=borde, width=int(max(2, .05 * r * S)))

    def mezcla(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    izq, der = (-0.75, -0.80), (0.92, -0.50)   # donde apoya el gorro
    ancho = int(.07 * r * S)
    if efecto == "navidad":
        rojo, osc, blanco = "#D62839", "#8E1220", "#FFFFFF"
        cuerpo = [P(*izq), P(0.30, -2.20), P(1.70, -1.55), P(*der)]
        d.polygon(cuerpo, fill=rojo)
        d.line(cuerpo + [cuerpo[0]], fill=osc, width=ancho, joint="curve")
        d.line([P(*izq), P(*der)], fill=osc, width=int(.62 * r * S))
        d.line([P(*izq), P(*der)], fill=blanco, width=int(.50 * r * S))
        for e in (izq, der):
            bola(e[0], e[1], .25, blanco, osc)
        d.line([P(*izq), P(*der)], fill=blanco, width=int(.46 * r * S))
        bola(1.70, -1.55, .33, blanco, osc)
    elif efecto in ("anonuevo", "carnaval"):
        if efecto == "anonuevo":
            base, bandas, pom, osc = "#FFC93C", ["#FFFFFF", "#E0A100"], "#FFFFFF", "#8A6400"
        else:
            base, bandas, pom, osc = "#FF3B6B", ["#FFD166", "#2EC4B6"], "#7B5CFF", "#7A1030"
        punta = (0.42, -2.05)
        d.polygon([P(*izq), P(*punta), P(*der)], fill=base)
        for (t0, t1), c in zip(((.22, .40), (.58, .74)), bandas):
            d.polygon([P(*mezcla(izq, punta, t0)), P(*mezcla(izq, punta, t1)),
                       P(*mezcla(der, punta, t1)), P(*mezcla(der, punta, t0))], fill=c)
        d.line([P(*izq), P(*punta), P(*der), P(*izq)], fill=osc, width=ancho, joint="curve")
        bola(punta[0], punta[1], .27, pom, osc)
    elif efecto == "amor":
        pts = []
        for i in range(60):
            t = 2 * math.pi * i / 60
            hx = 16 * math.sin(t) ** 3
            hy = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            pts.append(P(1.45 + hx * .045, -1.55 + hy * .045))
        d.polygon(pts, fill="#E63946")
        d.line(pts + [pts[0]], fill="#8E1220", width=ancho, joint="curve")

    capa = capa.resize(im.size, Image.LANCZOS)
    salida = im.convert("RGBA")
    salida.alpha_composite(capa)
    return salida


# Cabeza del pato en el logo blanco YA recortado al trazo (554x487).
CABEZA_LOGO_BLANCO = (242, 127, 52)


def logo_b64(umbral=60, efecto=None):
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
        # Las coordenadas de la cabeza valen para ESTE recorte; si el logo
        # cambia y el recorte sale de otro tamano, mejor sin gorro que torcido.
        if efecto and im.size == (554, 487):
            im = accesorio_logo(im, *CABEZA_LOGO_BLANCO, efecto)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _destello(x, y, r, color, op):
    """Estrella de cuatro puntas (el brillo tipico de una luz)."""
    k = r * 0.22
    return (f'<path d="M{x:.0f},{y - r:.0f} L{x + k:.1f},{y - k:.1f} L{x + r:.0f},{y:.0f} '
            f'L{x + k:.1f},{y + k:.1f} L{x:.0f},{y + r:.0f} L{x - k:.1f},{y + k:.1f} '
            f'L{x - r:.0f},{y:.0f} L{x - k:.1f},{y - k:.1f}Z" fill="{color}" opacity="{op:.2f}"/>')


def _libre(x, y):
    """Fuera de la esquina del logo: ahi no se dibuja ningun adorno."""
    return not (x < 300 and y < 320)


def efecto_svg(nombre):
    """Adorno para las fechas especiales (campo `efecto` de posts.yaml).

    Va dibujado ENCIMA de la foto real, no la sustituye: la finca sigue siendo
    la finca y la fecha se nota. Todo queda en la mitad de arriba para no
    pelear con el titular, y fuera de la esquina del logo.

    La semilla es el nombre del efecto: el mismo post se renderiza igual en
    Windows y en el runner, y un re-render no mueve los adornos de sitio.
    """
    import math
    import random
    if not nombre:
        return ""
    nombre = str(nombre).lower()
    rnd = random.Random(nombre)
    p = ['<svg class="efecto" xmlns="http://www.w3.org/2000/svg" '
         f'viewBox="0 0 {W} {H}" width="{W}" height="{H}"><defs>'
         '<filter id="halo" x="-200%" y="-200%" width="500%" height="500%">'
         '<feGaussianBlur stdDeviation="9"/></filter>'
         '<filter id="suave" x="-50%" y="-50%" width="200%" height="200%">'
         '<feGaussianBlur stdDeviation="2.2" result="b"/><feMerge>'
         '<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
         '</defs>']

    if nombre == "navidad":
        # Guirnalda de luces colgada del borde superior + destellos dorados.
        colores = ["#E63946", "#FFD166", "#2DC653", "#F2EDE4"]
        tramo, y0, yc = W / 5, 12, 52
        d = f"M0,{y0}" + "".join(
            f" Q{tramo * (i + .5):.0f},{yc} {tramo * (i + 1):.0f},{y0}" for i in range(5))
        p.append(f'<path d="{d}" fill="none" stroke="#1d2b1f" stroke-width="4"/>')
        n = 0
        for i in range(5):
            for t in (0.14, 0.38, 0.62, 0.86):
                x = tramo * (i + t)
                y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * yc + t * t * y0
                c = colores[n % len(colores)]
                n += 1
                p.append(f'<circle cx="{x:.0f}" cy="{y + 17:.0f}" r="20" fill="{c}" '
                         f'opacity=".75" filter="url(#halo)"/>')
                p.append(f'<rect x="{x - 4:.0f}" y="{y - 1:.0f}" width="8" height="8" fill="#1d2b1f"/>')
                p.append(f'<ellipse cx="{x:.0f}" cy="{y + 18:.0f}" rx="9" ry="13" fill="{c}"/>')
                p.append(f'<ellipse cx="{x - 3:.0f}" cy="{y + 13:.0f}" rx="2.5" ry="4" fill="#fff" opacity=".7"/>')
        hechos = 0
        while hechos < 34:
            x, y = rnd.uniform(30, W - 30), rnd.uniform(110, 760)
            if not _libre(x, y):
                continue
            hechos += 1
            r = rnd.uniform(7, 26) * (1 - y / 1500)
            p.append(_destello(x, y, r, rnd.choice(["#FFE29A", "#F2EDE4", "#FFD166"]),
                               rnd.uniform(.45, .95)))
    elif nombre == "anonuevo":
        # Fuegos artificiales en el cielo + chispas.
        for cx, cy, r, c in [(790, 300, 200, "#FFD166"), (300, 470, 150, "#F2EDE4"),
                             (640, 640, 110, "#FF8C61"), (960, 600, 90, "#FFE29A")]:
            g = ['<g filter="url(#suave)">']
            rayos = 22 if r > 120 else 16
            for k in range(rayos):
                a = 2 * math.pi * k / rayos
                for r1, r2, w_, op in ((.22, .62, 5, .95), (.70, 1.0, 3.5, .7)):
                    g.append(f'<line x1="{cx + r * r1 * math.cos(a):.0f}" y1="{cy + r * r1 * math.sin(a):.0f}" '
                             f'x2="{cx + r * r2 * math.cos(a):.0f}" y2="{cy + r * r2 * math.sin(a):.0f}" '
                             f'stroke="{c}" stroke-width="{w_}" stroke-linecap="round" opacity="{op}"/>')
                g.append(f'<circle cx="{cx + r * 1.08 * math.cos(a):.0f}" '
                         f'cy="{cy + r * 1.08 * math.sin(a):.0f}" r="4" fill="{c}"/>')
            g.append("</g>")
            p.append("".join(g))
        hechos = 0
        while hechos < 26:
            x, y = rnd.uniform(30, W - 30), rnd.uniform(60, 800)
            if not _libre(x, y):
                continue
            hechos += 1
            p.append(_destello(x, y, rnd.uniform(6, 18), "#FFE29A", rnd.uniform(.4, .9)))
    elif nombre == "carnaval":
        # Papelillo cayendo: mas denso arriba, se va aclarando hacia el titular.
        colores = ["#FF3B6B", "#FFD166", "#2EC4B6", "#7B5CFF", "#FF8C42", "#F2EDE4", "#3DDC84"]
        hechos = 0
        while hechos < 130:
            x, y = rnd.uniform(0, W), abs(rnd.gauss(0, 330))
            if y > 820 or not _libre(x, y):
                continue
            hechos += 1
            c, a = rnd.choice(colores), rnd.uniform(0, 180)
            if rnd.random() < .3:
                p.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.uniform(6, 11):.0f}" fill="{c}" opacity=".92"/>')
            else:
                w_, h_ = rnd.uniform(12, 24), rnd.uniform(7, 13)
                p.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w_:.0f}" height="{h_:.0f}" rx="2" '
                         f'fill="{c}" opacity=".92" transform="rotate({a:.0f} {x:.0f} {y:.0f})"/>')
        for i in range(4):  # serpentinas
            x = 380 + i * 190 + rnd.uniform(-30, 30)
            c = colores[i]
            p.append(f'<path d="M{x:.0f},-10 q40,45 0,90 t0,90 t0,90" fill="none" stroke="{c}" '
                     f'stroke-width="7" stroke-linecap="round" opacity=".9"/>')
    elif nombre == "amor":
        # Corazones flotando.
        colores = ["#FF4D6D", "#FF8FA3", "#F2EDE4", "#E63946"]
        hechos = 0
        while hechos < 20:
            x, y = rnd.uniform(40, W - 40), rnd.uniform(50, 720)
            if not _libre(x, y):
                continue
            hechos += 1
            s = rnd.uniform(.7, 2.4) * (1 - y / 1600)
            p.append(f'<path transform="translate({x:.0f} {y:.0f}) rotate({rnd.uniform(-22, 22):.0f}) scale({s:.2f})" '
                     'd="M0,10 C-28,-14 -14,-34 0,-18 C14,-34 28,-14 0,10Z" '
                     f'fill="{rnd.choice(colores)}" opacity="{rnd.uniform(.6, .95):.2f}" filter="url(#suave)"/>')
    else:
        morir(f"efecto desconocido: {nombre!r}. Validos: navidad, anonuevo, carnaval, amor")

    p.append("</svg>")
    return "".join(p)


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
            .replace("{{LOGO}}", logo_b64(efecto=fila.get("efecto")))
            .replace("{{FOCO}}", foco)
            .replace("{{TITULO}}", titulo)
            .replace("{{CLASE}}", "festivo" if fila.get("efecto") else "")
            .replace("{{EFECTO}}", efecto_svg(fila.get("efecto")))
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
        # Sin esto la captura puede salir antes de que document.fonts.ready
        # resuelva y el titular quede sin ajustar.
        "--virtual-time-budget=5000",
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
