import hashlib
import re

import pandas as pd

from utils import sanitize_filename, logger
from processor_utils import analizar_oferta

# Orden de columnas del Excel maestro (las de análisis van entre Pageweb y oferta)
COLUMNAS_EXCEL = [
    "Fecha", "Nombre", "Empresa", "Ubicacion", "Tipo", "Pageweb",
    "puntaje_data", "keyword", "ingles", "remoto", "hibrido", "presencial",
    "part_time", "practica", "trainee", "automatizacion", "oferta"
]


def _id_oferta(url: str) -> str:
    """Obtiene un identificador único de la oferta a partir de su URL."""
    m = re.search(r"(\d+)\.html$", url)
    if m:
        return m.group(1)
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:8]


def _ruta_archivo(carpeta_destino, titulo: str, clean_url: str):
    """Nombre de archivo único: título sanitizado + id de la oferta (evita colisiones)."""
    return carpeta_destino / f"{sanitize_filename(titulo)[:120]}_{_id_oferta(clean_url)}.txt"


async def scrapear_pagina(page, fecha_hoy, lista_datos, carpeta_destino, urls_vistas):
    """
    Extrae la información de todas las ofertas directamente desde el listado de la página actual.

    urls_vistas es un set compartido entre páginas y precargado con el historial:
    evita duplicados al paginar y re-procesar ofertas de días anteriores.
    """
    # Esperar a que el listado cargue antes de leerlo (evita terminar antes de
    # tiempo cuando la página tarda en renderizar las ofertas).
    try:
        await page.wait_for_selector('a[href*="/empleos/"]', timeout=15000)
    except Exception:
        logger.warning("No se detectaron ofertas en la página (timeout esperando el listado).")
        return

    # Cada oferta en el listado está contenida en un bloque que tiene el enlace a /empleos/
    elementos = await page.locator('a[href*="/empleos/"]').all()

    nuevas = 0
    omitidas = 0

    for el in elementos:
        try:
            url = await el.get_attribute("href")
            if not url or "/empleos/" not in url:
                continue

            if url.startswith("/"):
                url = "https://www.laborum.cl" + url

            # Limpiar URL y evitar duplicados (algunas cards tienen varios links a la misma oferta,
            # y las ofertas de días anteriores ya vienen precargadas desde el historial)
            clean_url = url.split('?')[0].rstrip('/')
            if clean_url in urls_vistas:
                omitidas += 1
                continue
            urls_vistas.add(clean_url)

            # --- EXTRACCIÓN DIRECTA DESDE EL LISTADO ---
            # Título: El primer H2 dentro del contexto de la oferta
            titulo_el = el.locator('h2').first
            titulo = await titulo_el.text_content() if await titulo_el.count() > 0 else "sin_titulo"
            titulo = titulo.strip().replace("/", "-")

            # Descripción: El primer P dentro del contexto de la oferta (resumen)
            desc_el = el.locator('p').first
            descripcion = await desc_el.text_content() if await desc_el.count() > 0 else "N/A"
            descripcion = descripcion.strip()

            # Empresa: Suele estar en un H3 o span dentro de la card
            empresa_el = el.locator('h3').first
            empresa = await empresa_el.text_content() if await empresa_el.count() > 0 else "N/A"
            empresa = empresa.strip()

            # Análisis por puntaje/keywords (se incluye el título porque el
            # resumen del listado es corto y el título aporta señal)
            analisis = analizar_oferta(f"{titulo}\n{descripcion}")

            # Guardar en la lista
            lista_datos.append({
                "Fecha": fecha_hoy,
                "Nombre": titulo,
                "Empresa": empresa,
                "Ubicacion": "Ver en descripción",  # No siempre está explícita en el listado
                "Tipo": "N/A",
                "Pageweb": clean_url,
                **analisis,
                "oferta": descripcion
            })

            # Guardar archivo individual con el resumen
            archivo = _ruta_archivo(carpeta_destino, titulo, clean_url)
            archivo.write_text(
                f"URL: {clean_url}\nEMPRESA: {empresa}\n\nDESCRIPCIÓN:\n{descripcion}",
                encoding="utf-8"
            )

            nuevas += 1

        except Exception as e:
            logger.error(f"Error al extraer oferta del listado: {e}")

    logger.info(f"Página procesada: {nuevas} ofertas nuevas, {omitidas} ya conocidas/duplicadas.")
    return nuevas


async def ir_siguiente_pagina(page) -> bool:
    """
    Intenta navegar a la siguiente página del paginador.
    """
    try:
        # En Laborum, el botón siguiente suele ser un enlace con el icono 'caret-right'
        # o simplemente el enlace que sigue al número de página actual.
        boton_siguiente = page.locator('a:has(i[class*="caret-right"]), a[class*="caret-right"]').last

        if await boton_siguiente.count() == 0:
            return False

        # En la última página el botón existe pero está deshabilitado: detectarlo
        # aquí evita esperar el timeout completo del click.
        if await boton_siguiente.get_attribute("aria-disabled") == "true" \
                or await boton_siguiente.get_attribute("disabled") is not None:
            return False

        # Scroll hasta el botón para asegurar que sea clickable
        await boton_siguiente.scroll_into_view_if_needed()
        await boton_siguiente.click()
        # Esperar carga
        await page.wait_for_load_state("networkidle")
        return True
    except Exception as e:
        logger.warning(f"No se pudo navegar a la siguiente página: {e}")

    return False


def guardar_excel(lista_datos, output_path):
    try:
        df = pd.DataFrame(lista_datos)
        # Ordenar columnas: primero las conocidas, luego cualquier extra
        orden = [c for c in COLUMNAS_EXCEL if c in df.columns]
        orden += [c for c in df.columns if c not in orden]
        df = df[orden]
        df.to_excel(output_path, index=False)
        logger.info(f"Excel guardado exitosamente en {output_path}")
    except Exception as e:
        logger.error(f"Error al guardar Excel: {e}")
