import hashlib
import re

import pandas as pd

from utils import sanitize_filename, logger


def _id_oferta(url: str) -> str:
    """Obtiene un identificador único de la oferta a partir de su URL."""
    m = re.search(r"(\d+)\.html$", url)
    if m:
        return m.group(1)
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:8]


def _ruta_archivo(carpeta_destino, titulo: str, clean_url: str):
    """Nombre de archivo único: título sanitizado + id de la oferta (evita colisiones)."""
    return carpeta_destino / f"{sanitize_filename(titulo)[:120]}_{_id_oferta(clean_url)}.txt"


def _campo(prev: dict, clave: str, default: str = "N/A") -> str:
    """Lee un campo de una fila previa del Excel tolerando NaN/valores no string."""
    valor = prev.get(clave)
    if isinstance(valor, str) and valor.strip():
        return valor
    return default


async def scrapear_pagina(page, fecha_hoy, lista_datos, carpeta_destino, urls_vistas, datos_previos=None):
    """
    Extrae la información de todas las ofertas directamente desde el listado de la página actual.

    urls_vistas es un set compartido entre páginas: evita duplicados cuando una
    oferta se desplaza de una página a otra durante la paginación.
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
    reutilizadas = 0

    for el in elementos:
        try:
            url = await el.get_attribute("href")
            if not url or "/empleos/" not in url:
                continue

            if url.startswith("/"):
                url = "https://www.laborum.cl" + url

            # Limpiar URL y evitar duplicados (algunas cards tienen varios links a la misma oferta)
            clean_url = url.split('?')[0].rstrip('/')
            if clean_url in urls_vistas:
                continue
            urls_vistas.add(clean_url)

            # Si la oferta ya fue procesada en una ejecución anterior, reutilizamos
            # sus datos (pueden ser más completos) en lugar de volver a extraerla.
            if datos_previos and clean_url in datos_previos:
                prev = datos_previos[clean_url]
                titulo = _campo(prev, "Nombre", "sin_titulo")
                texto = _campo(prev, "oferta", "")

                archivo = _ruta_archivo(carpeta_destino, titulo, clean_url)
                if not archivo.exists():
                    archivo.write_text(texto, encoding="utf-8")

                lista_datos.append({
                    "Fecha": fecha_hoy,
                    "Nombre": titulo,
                    "Empresa": _campo(prev, "Empresa"),
                    "Ubicacion": _campo(prev, "Ubicacion"),
                    "Tipo": _campo(prev, "Tipo"),
                    "Pageweb": clean_url,
                    "oferta": texto
                })
                reutilizadas += 1
                continue

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

            # Guardar en la lista
            lista_datos.append({
                "Fecha": fecha_hoy,
                "Nombre": titulo,
                "Empresa": empresa,
                "Ubicacion": "Ver en descripción",  # No siempre está explícita en el listado
                "Tipo": "N/A",
                "Pageweb": clean_url,
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

    logger.info(f"Página procesada: {nuevas} ofertas nuevas, {reutilizadas} reutilizadas.")


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
        df.to_excel(output_path, index=False)
        logger.info(f"Excel guardado exitosamente en {output_path}")
    except Exception as e:
        logger.error(f"Error al guardar Excel: {e}")
