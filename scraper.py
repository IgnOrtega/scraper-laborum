import html
import re
import time
import unicodedata
from datetime import datetime

import pandas as pd
import requests

from config import FECHA_HOY
from utils import sanitize_filename, logger
from processor_utils import analizar_oferta

API_URL = "https://www.laborum.cl/api/avisos/searchNormalizado"
PAGE_SIZE = 50
MAX_INTENTOS = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "x-site-id": "BMCL",
    "Origin": "https://www.laborum.cl",
}

# Orden de columnas del Excel maestro (las de análisis van entre Pageweb y oferta)
COLUMNAS_EXCEL = [
    "Fecha", "Nombre", "Empresa", "Ubicacion", "Tipo", "Pageweb",
    "puntaje_data", "keyword", "ingles", "remoto", "hibrido", "presencial",
    "part_time", "practica", "trainee", "automatizacion", "oferta"
]


def crear_session(base_url):
    """
    Crea la sesión HTTP y visita primero la página del listado: el sitio entrega
    ahí las cookies que la API exige para responder.
    """
    session = requests.Session()
    session.headers.update({**HEADERS, "Referer": base_url})
    resp = session.get(base_url, timeout=30)
    resp.raise_for_status()
    return session


def filtro_fecha_desde_url(base_url):
    """
    Deriva el filtro de fecha de la API desde el slug de BASE_URL.
    Ej: '.../empleos-publicacion-menor-a-2-dias.html' -> 'publicacion-menor-a-2-dias'
    (el mismo valor que acepta la API en el filtro 'dias_fecha_publicacion').
    """
    m = re.search(r"empleos-(publicacion[a-z0-9\-]*)\.html", base_url)
    if not m:
        logger.warning("No se pudo derivar el filtro de fecha desde BASE_URL; se buscará sin filtro.")
        return None
    return m.group(1)


def obtener_pagina(session, filtro_fecha, page, page_size=PAGE_SIZE):
    """
    Pide una página de resultados a la API (con reintentos).
    Devuelve el JSON de la respuesta o None si todos los intentos fallan.
    """
    filtros = [{"id": "dias_fecha_publicacion", "value": filtro_fecha}] if filtro_fecha else []
    body = {"filtros": filtros, "busquedaExtendida": False}
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            resp = session.post(
                API_URL,
                params={"pageSize": page_size, "page": page},
                json=body,
                timeout=30
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Intento {intento}/{MAX_INTENTOS} fallido para la página {page}: {e}")
            if intento < MAX_INTENTOS:
                time.sleep(2 * intento)
    logger.error(f"No se pudo obtener la página {page}.")
    return None


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower()).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto or "oferta"


def url_oferta(titulo: str, id_aviso: str) -> str:
    """Reconstruye la URL pública de la oferta (mismo formato que usa el sitio)."""
    return f"https://www.laborum.cl/empleos/{_slug(titulo)}-{id_aviso}.html"


def _fecha_iso(fecha_str):
    """Convierte 'DD-MM-YYYY' (formato de la API) a 'YYYY-MM-DD'."""
    try:
        return datetime.strptime(fecha_str, "%d-%m-%Y").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return FECHA_HOY


def procesar_avisos(avisos, lista_datos, carpeta_destino, ids_vistos):
    """
    Procesa los avisos de una página de la API: análisis por puntaje, archivo .txt
    individual y fila para el Excel maestro.

    ids_vistos es un set compartido y precargado con el historial: evita duplicados
    y re-procesar ofertas de días anteriores.
    """
    nuevas = 0
    omitidas = 0

    for aviso in avisos:
        try:
            id_aviso = str(aviso.get("id") or "")
            if not id_aviso:
                continue
            if id_aviso in ids_vistos:
                omitidas += 1
                continue
            ids_vistos.add(id_aviso)

            titulo = html.unescape(aviso.get("titulo") or "sin_titulo").strip().replace("/", "-")
            empresa = (aviso.get("empresa") or "Confidencial").strip()
            ubicacion = (aviso.get("localizacion") or "N/A").strip()
            tipo = (aviso.get("tipoTrabajo") or "N/A").strip()
            modalidad = (aviso.get("modalidadTrabajo") or "").strip()
            texto = html.unescape(aviso.get("detalle") or "").strip()

            link = url_oferta(titulo, id_aviso)

            # El análisis incluye título, modalidad y tipo además de la descripción,
            # para no perder señal que solo aparece en esos campos.
            analisis = analizar_oferta(f"{titulo}\n{modalidad} {tipo}\n{texto}")

            archivo = carpeta_destino / f"{sanitize_filename(titulo)[:120]}_{id_aviso}.txt"
            archivo.write_text(
                f"URL: {link}\nEMPRESA: {empresa}\nUBICACION: {ubicacion}\nTIPO: {tipo}"
                f"{' - ' + modalidad if modalidad else ''}\n\nDESCRIPCIÓN:\n{texto}",
                encoding="utf-8"
            )

            lista_datos.append({
                "Fecha": _fecha_iso(aviso.get("fechaPublicacion")),
                "Nombre": titulo,
                "Empresa": empresa,
                "Ubicacion": ubicacion,
                "Tipo": f"{tipo} - {modalidad}" if modalidad else tipo,
                "Pageweb": link,
                **analisis,
                "oferta": texto
            })
            nuevas += 1

        except Exception as e:
            logger.error(f"Error al procesar aviso: {e}")

    logger.info(f"Página procesada: {nuevas} ofertas nuevas, {omitidas} ya conocidas/duplicadas.")
    return nuevas


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
