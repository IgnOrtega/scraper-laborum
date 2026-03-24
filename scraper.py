import pandas as pd
from pathlib import Path
from utils import sanitize_filename, centrar_pantalla, logger, async_retry
import httpx
from bs4 import BeautifulSoup
import asyncio
from fake_useragent import UserAgent
from config import MAX_RETRIES, MAX_CONCURRENT_REQUESTS, RETRY_DELAY

ua = UserAgent()

@async_retry(max_retries=MAX_RETRIES, delay=RETRY_DELAY)
async def bajar_datos_oferta(client, url, carpeta_destino):
    """
    Descarga el HTML de una oferta laboral y extrae título, empresa, ubicación y texto.
    """
    headers = {
        "User-Agent": ua.random
    }

    response = await client.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Título: Primer H1 estrictamente dentro de header-component
    header_container = soup.find(id="header-component")
    if header_container:
        titulo_tag = header_container.find('h1')
        titulo = titulo_tag.get_text(strip=True).replace("/", "-") if titulo_tag else "sin_titulo"
    else:
        titulo = "sin_titulo"

    # Empresa: H3 dentro del mismo header-component
    empresa_tag = header_container.find('h3') if header_container else None
    empresa = empresa_tag.get_text(strip=True) if empresa_tag else "N/A"

    # Ubicación: Buscamos el texto cerca del icono de mapa (pin)
    ubicacion = "N/A"
    icon_map = soup.select_one('i[name*="location-pin"]') or soup.find('i', class_=lambda x: x and 'location' in x)
    if icon_map:
        # Intentamos obtener el texto del contenedor padre o hermano
        parent = icon_map.parent
        if parent:
            ubicacion = parent.get_text(strip=True)

    # Tipo de jornada (Full-time, etc): Buscamos cerca del icono de reloj
    tipo = "N/A"
    icon_clock = soup.select_one('i[name*="clock"]')
    if icon_clock and icon_clock.parent:
        tipo = icon_clock.parent.get_text(strip=True)

    # Contenido de la oferta: El ID 'ficha-detalle' es el más estable
    detalle_container = soup.find(id="ficha-detalle")
    if detalle_container:
        # Usamos el contenedor como contexto para buscar párrafos y listas
        # Esto asegura que solo traemos el texto relevante de la descripción
        elementos_texto = detalle_container.find_all(['p', 'li'])
        
        # Extraemos el texto de cada elemento, eliminando duplicados si hay anidamiento
        lineas = []
        for el in elementos_texto:
            txt = el.get_text(strip=True)
            if txt and txt not in lineas:
                lineas.append(txt)
        
        texto = "\n".join(lineas)
    else:
        # Fallback por si el ID cambia (aunque en Laborum es muy estable)
        texto = "Contenido no disponible"

    if not texto.strip() or len(texto) < 20:
        # Si el texto es muy corto, intentamos capturar todo el body del artículo
        main_content = soup.select_one('article') or soup.select_one('main')
        if main_content:
            texto = main_content.get_text(separator="\n", strip=True)

    archivo = carpeta_destino / f"{sanitize_filename(titulo)}.txt"
    archivo.write_text(texto, encoding="utf-8")
    print("---"*100)
    print(titulo)
    print(texto)
    print("---"*100)
    
    return {
        "Nombre": titulo,
        "Empresa": empresa,
        "Ubicacion": ubicacion,
        "Tipo": tipo,
        "Texto": texto
    }


async def obtener_info_oferta(semaphore, client, url, fecha_hoy, lista_datos, carpeta_destino, datos_previos=None):
    """
    Extrae la información de una oferta de manera asíncrona.
    """    
    async with semaphore:
        try:
            # Normalizar URL para comparación
            clean_url = url.split('?')[0].rstrip('/')
            
            if datos_previos and clean_url in datos_previos:
                logger.info(f"Reutilizando datos previos para: {clean_url}")
                prev = datos_previos[clean_url]
                
                titulo = str(prev.get("Nombre", "sin_titulo"))
                texto = str(prev.get("oferta", ""))
                
                archivo = carpeta_destino / f"{sanitize_filename(titulo)}.txt"
                if not archivo.exists():
                    archivo.write_text(texto, encoding="utf-8")

                lista_datos.append({
                    "Fecha": fecha_hoy,
                    "Nombre": prev.get("Nombre", "N/A"),
                    "Empresa": prev.get("Empresa", "N/A"),
                    "Ubicacion": prev.get("Ubicacion", "N/A"),
                    "Tipo": prev.get("Tipo", "N/A"),
                    "Pageweb": url,
                    "oferta": texto
                })
                return

            logger.info(f"Procesando: {url}")
            datos = await bajar_datos_oferta(client, url, carpeta_destino)

            lista_datos.append({
                "Fecha": fecha_hoy,
                "Nombre": datos["Nombre"],
                "Empresa": datos["Empresa"],
                "Ubicacion": datos["Ubicacion"],
                "Tipo": datos["Tipo"],
                "Pageweb": url,
                "oferta": datos["Texto"]
            })
        except Exception as e:
            logger.error(f"Error al procesar la oferta {url}: {e}")


async def scrapear_pagina(page, context, fecha_hoy, lista_datos, carpeta_destino, datos_previos=None):
    """
    Extrae la información de todas las ofertas directamente desde el listado de la página actual.
    """    
    # Cada oferta en el listado está contenida en un bloque que tiene el enlace a /empleos/
    # Usamos el localizador para obtener todos los contenedores de ofertas
    ofertas_locator = page.locator('div[id="listado-avisos"] > div, #listado-avisos a[href*="/empleos/"]')
    
    # En Laborum, usualmente el enlace envuelve o está dentro de la "card"
    # Vamos a obtener todos los elementos que parecen ser una oferta individual
    elementos = await page.locator('a[href*="/empleos/"]').all()
    
    urls_procesadas = set()
    count = 0

    for el in elementos:
        try:
            url = await el.get_attribute("href")
            if not url or "/empleos/" not in url:
                continue
            
            if url.startswith("/"):
                url = "https://www.laborum.cl" + url
            
            # Limpiar URL y evitar duplicados (algunas cards tienen varios links a la misma oferta)
            clean_url = url.split('?')[0]
            if clean_url in urls_procesadas:
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
                "Ubicacion": "Ver en descripción", # No siempre está explícita en el listado
                "Tipo": "N/A",
                "Pageweb": clean_url,
                "oferta": descripcion
            })

            # Guardar archivo individual con el resumen
            archivo = carpeta_destino / f"{sanitize_filename(titulo)}.txt"
            archivo.write_text(f"URL: {clean_url}\nEMPRESA: {empresa}\n\nDESCRIPCIÓN:\n{descripcion}", encoding="utf-8")

            urls_procesadas.add(clean_url)
            count += 1
            
        except Exception as e:
            logger.error(f"Error al extraer oferta del listado: {e}")

    logger.info(f"Se extrajeron {count} ofertas directamente de esta página.")


async def ir_siguiente_pagina(page) -> bool:
    """
    Intenta navegar a la siguiente página del paginador.
    """    
    try:
        # En Laborum, el botón siguiente suele ser un enlace con el icono 'caret-right'
        # o simplemente el enlace que sigue al número de página actual.
        boton_siguiente = page.locator('a:has(i[class*="caret-right"]), a[class*="caret-right"]').last
        
        if await boton_siguiente.count() > 0:
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
