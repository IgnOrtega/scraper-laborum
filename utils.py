import re
import argparse
import logging
import pandas as pd
from pathlib import Path


def setup_logger(name: str = "laborum_scraper", log_file: str = "scraper.log", level=logging.INFO):
    """
    Configura y devuelve un logger.
    """
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    handler = logging.FileHandler(log_file, encoding='utf-8')
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        logger.addHandler(handler)
        logger.addHandler(console_handler)

    return logger


logger = setup_logger()


def obtener_datos_previos(summary_base_dir: Path) -> dict:
    """
    Busca el archivo summary_data.xlsx más reciente y devuelve un diccionario {url: datos}.
    Las URLs se normalizan (sin query string ni slash final) para que coincidan
    con las claves que usa el scraper.
    """
    if not summary_base_dir.exists():
        return {}

    # Listar carpetas de fechas y ordenarlas
    carpetas_fechas = sorted([d for d in summary_base_dir.iterdir() if d.is_dir()])

    if not carpetas_fechas:
        return {}

    # Empezamos por la más reciente
    for carpeta in reversed(carpetas_fechas):
        archivo_excel = carpeta / "summary_data.xlsx"
        if archivo_excel.exists():
            try:
                logger.info(f"Cargando datos previos desde {archivo_excel}")
                df = pd.read_excel(archivo_excel)
                datos = {}
                for url, fila in df.set_index('Pageweb').to_dict('index').items():
                    if not isinstance(url, str):
                        continue
                    clean_url = url.split('?')[0].rstrip('/')
                    datos[clean_url] = fila
                return datos
            except Exception as e:
                logger.error(f"Error al cargar el archivo previo {archivo_excel}: {e}")

    return {}


def str2bool(value):
    if isinstance(value, bool):
        return value
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError("Booleano esperado.")


def sanitize_filename(filename: str) -> str:
    """
    Limpia un string para que pueda ser usado como nombre de archivo.
    """
    return re.sub(r'[\\/:*?"<>|]', '_', filename)
