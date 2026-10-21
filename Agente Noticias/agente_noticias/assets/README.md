# Assets de marca

## Header del correo

- Archivo: `header_noticias_ia.png` (1200x220 px, se muestra a 600 px de ancho, fluido en movil).
- Fondo naranja WIN + logo blanco + "NOTICIAS IA", esquinas superiores redondeadas transparentes.
- Es una imagen porque Outlook web en modo oscuro cambia los fondos naranjas a rojo
  (las imagenes no se recolorean). Debe pesar menos de 100 KB (Outlook web descarta
  imagenes inline mas grandes).
- Se genera con `uv run python scripts/build_header.py`; regeneralo si cambia el logo.

Si el archivo no existe, el correo usa un texto "win Noticias IA" como respaldo.

## Logo de Win

- Archivo: `win_logo.png` (lo usa `build_header.py` y la webapp).
- Version: logo **WIN en blanco + claim "EL INTERNET DE LOS WINNERS"**, PNG con
  **fondo transparente**, recortado sin margen (440x227 px).
