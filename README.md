# finca-guamito-media

Publica un post diario alterno en [@fincaelguamito](https://instagram.com/fincaelguamito)
sin depender de que haya un ordenador encendido.

GitHub Actions renderiza la imagen del dia, la sirve por GitHub Pages y la
publica con la Graph API de Meta. El repo es publico porque Instagram descarga
la imagen por URL: no se le suben bytes.

## Como funciona

```
21:00 UTC (17:00 Venezuela), todos los dias
  |
  |-- hoy esta en posts.yaml?  no -> termina, hoy no toca
  |
  |-- render_post.py     foto + titulo -> JPEG 1080x1350
  |-- commit a img/      GitHub Pages lo sirve
  |-- espera a que la URL responda 200
  |-- publicar_finca.py  Graph API
```

La cadencia (un dia si, un dia no) vive en `posts.yaml`, no en el cron. El cron
corre a diario y solo publica si la fecha de hoy esta en la cola.

## Estructura

| | |
|---|---|
| `posts.yaml` | la cola: fecha, foto, titulo, caption, hashtags |
| `plantillas/` | `base.css` con los tokens de marca y `full.html` |
| `FUTURAS SEMANAS/IMAGENES/` | las fotos de origen que usa la cola |
| `img/` | los JPEG ya publicados, servidos por Pages |

## Configuracion

Secrets del repo:

| | |
|---|---|
| `FB_PAGE_TOKEN` | token del system user de Meta (no caduca) |
| `IG_USER_ID` | id de la cuenta de Instagram Business |

Variable del repo:

| | |
|---|---|
| `FINCA_PAGES_BASE_URL` | `https://xupratechnologies.github.io/finca-guamito-media` |

## Anadir posts

Editar `posts.yaml` y hacer commit. No hay revision antes de publicar, asi que
lo que se encola sale tal cual: el control de calidad esta al encolar.

## Probar sin publicar

Actions -> Publicar en Instagram -> Run workflow, marcando **dry_run**. Crea el
contenedor en Meta pero no lo publica; los contenedores caducan solos en 24 h.
