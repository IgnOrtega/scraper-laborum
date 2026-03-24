
import os
from bs4 import BeautifulSoup
from pathlib import Path

def probar_extraccion(ruta_html):
    print(f"\n--- Analizando: {ruta_html} ---")
    with open(ruta_html, "r", encoding="utf-8") as f:
        html = f.read()
    
    soup = BeautifulSoup(html, "html.parser")

    # Título: El único H1 dentro del header de la oferta
    titulo_tag = soup.select_one('#header-component h1') or soup.find('h1')
    titulo = titulo_tag.get_text(strip=True) if titulo_tag else "sin_titulo"

    # Empresa: H3 dentro del header
    empresa_tag = soup.select_one('#header-component h3')
    empresa = empresa_tag.get_text(strip=True) if empresa_tag else "N/A"

    # Ubicación: Buscamos el texto cerca del icono de mapa (pin)
    ubicacion = "N/A"
    icon_map = soup.select_one('i[name*="location-pin"]') or soup.find('i', class_=lambda x: x and 'location' in x)
    if icon_map:
        parent = icon_map.parent
        if parent:
            ubicacion = parent.get_text(strip=True)

    # Contenido de la oferta: El ID 'ficha-detalle'
    detalle_container = soup.find(id="ficha-detalle")
    if detalle_container:
        parrafos = detalle_container.find_all(['p', 'li'])
        texto = "\n".join([p.get_text(strip=True) for p in parrafos if p.get_text(strip=True)])
    else:
        texto = "Contenido no disponible"
    
    print("--"*100)
    print(titulo)
    print(texto)
    print("--"*100)

    print(f"TITULO: {titulo}")
    print(f"EMPRESA: {empresa}")
    print(f"UBICACION: {ubicacion}")
    print(f"TEXTO (Primeros 150 caracteres): {texto[:150]}...")
    return titulo

# Rutas de los archivos
oferta1 = Path("oferta 1/Jefa de Tienda - Mall Viña Outlet Park - marzo 2026 _ Laborum Chile.html")
oferta2 = Path("oferta 2/ASISTENTE DE DIRECTORIO Y GERENCIA - marzo 2026 _ Laborum Chile.html")

if oferta1.exists():
    probar_extraccion(oferta1)
if oferta2.exists():
    probar_extraccion(oferta2)
