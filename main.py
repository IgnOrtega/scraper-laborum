import asyncio
import argparse
import random
import math
from pathlib import Path

from config import BASE_URL, FECHA_HOY
from browser import iniciar_browser, cerrar_browser
from scraper import (
    scrapear_pagina,
    ir_siguiente_pagina,
    guardar_excel
)
from utils import str2bool, logger, obtener_datos_previos


async def main(DATA_DIR, HEADLESS_BOOL, MAX_PAGES=None, DELAY_EXPECTED=3.0):
    # Definición de rutas
    RAW_DATA_DIR = Path(DATA_DIR) / "laborum" / "raw_data" / FECHA_HOY
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    SUMMARY_BASE_DIR = Path(DATA_DIR) / "laborum" / "summary_data"
    SUMMARY_DATA_DIR = SUMMARY_BASE_DIR / FECHA_HOY
    SUMMARY_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Si MAX_PAGES es None o 0, recorremos todas (infinito)
    if not MAX_PAGES or MAX_PAGES <= 0:
        logger.info("Configurado para recorrer TODAS las páginas disponibles.")
        MAX_PAGES = float('inf')
    else:
        logger.info(f"Configurado para recorrer un máximo de {MAX_PAGES} páginas.")

    logger.info(f"Retraso configurado (Esperanza): {DELAY_EXPECTED}s con Varianza del 5%.")

    # Cargar datos de ejecuciones anteriores para evitar descargas innecesarias
    datos_previos = obtener_datos_previos(SUMMARY_BASE_DIR)
    if datos_previos:
        logger.info(f"Se encontraron {len(datos_previos)} ofertas previas para omitir descarga.")

    lista_datos = []
    urls_vistas = set()  # compartido entre páginas para no duplicar ofertas que se desplazan al paginar

    playwright, browser, context, page = await iniciar_browser(HEADLESS_BOOL)

    try:
        logger.info(f"Iniciando scraping en {BASE_URL}")
        await page.goto(BASE_URL, wait_until="networkidle")
        
        # Manejo de publicidad más robusto
        try:
            # Esperar a que el botón de cerrar aparezca si el modal es visible
            btn_close = page.get_by_role("button", name="Close").or_(page.locator("#notification_modal_link"))
            if await btn_close.is_visible(timeout=5000):
                logger.info("Cerrando publicidad detectada...")
                await btn_close.click()
        except Exception:
            logger.info("No se detectó publicidad o no se pudo cerrar.")

        pagina = 1
        while pagina <= MAX_PAGES:
            logger.info(f"Procesando página {pagina} de {MAX_PAGES if MAX_PAGES != float('inf') else 'todas'}...")

            await scrapear_pagina(
                page,
                FECHA_HOY,
                lista_datos,
                RAW_DATA_DIR,
                urls_vistas,
                datos_previos
            )

            # Verificar si alcanzamos el límite antes de intentar navegar
            if pagina >= MAX_PAGES:
                logger.info(f"Se alcanzó el límite de {MAX_PAGES} páginas.")
                break

            # Intentar navegar a la siguiente página
            if not await ir_siguiente_pagina(page):
                logger.info("No hay más páginas o se alcanzó el final. Finalizando...")
                break

            pagina += 1
            
            # CÁLCULO DE RETRASO CON DISTRIBUCIÓN UNIFORME
            # Varianza = 0.05 * Esperanza. Ancho del intervalo (b-a) = sqrt(0.6 * Esperanza)
            mu = DELAY_EXPECTED
            ancho = math.sqrt(0.6 * mu)
            a = mu - (ancho / 2)
            b = mu + (ancho / 2)
            
            retraso = random.uniform(max(0.1, a), b)
            logger.info(f"Esperando {retraso:.2f} segundos (Intervalo: [{a:.2f}, {b:.2f}]) antes de la siguiente página...")
            await asyncio.sleep(retraso)

    except Exception as e:
        logger.error(f"Error crítico durante la ejecución: {e}", exc_info=True)
    finally:
        try:
            await cerrar_browser(playwright, browser)
        except Exception as e:
            logger.warning(f"Error al cerrar el navegador: {e}")

        # Guardar dentro del finally: así no se pierde lo scrapeado si el
        # proceso se interrumpe (Ctrl+C) o falla a mitad de camino.
        if lista_datos:
            output_file = SUMMARY_DATA_DIR / "summary_data.xlsx"
            guardar_excel(lista_datos, output_file)
            logger.info(f"Scraping finalizado. {len(lista_datos)} ofertas procesadas.")
            logger.info(f"Datos guardados en {output_file}")
        else:
            logger.warning("No se encontraron datos para guardar.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scraper de Laborum con Playwright y Concurrencia.")
    parser.add_argument("--dir", type=str, required=True, help="Directorio raíz para los datos.")
    parser.add_argument(
        "--headless",
        type=str2bool,
        default=False,
        help="Ejecutar en modo headless (sin ventana)."
    )
    parser.add_argument(
        "--pages",
        "-p",
        type=int,
        default=None,
        help="Cantidad máxima de páginas a recorrer."
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=3.0,
        help="Tiempo esperado (Esperanza) de retraso entre páginas."
    )
    
    args = parser.parse_args()
    try:
        asyncio.run(main(args.dir, args.headless, args.pages, args.delay))
    except KeyboardInterrupt:
        logger.info("Proceso interrumpido por el usuario.")
# Delay sirve para esperar que cargue las ofertas de la pagina i, con i in {1,total paginas}
# si delay es bajo el scraper puede pensar que la pagina i no tiene ofertas y termina el proceso
# python "main.py" --dir "C:\Users\Nach\Desktop\datos" --headless "false" --pages 1 --delay 1.5
# python "main.py" --dir "C:\Users\Nach\Desktop\datos" --headless "false" --delay 0