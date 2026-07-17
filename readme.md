# Laborum Scraper 🚀

Scraper automatizado desarrollado con **Python** y **Playwright** para la extracción masiva de ofertas laborales desde el portal **Laborum.cl**.

El sistema está diseñado para navegar de forma asíncrona, manejar paginación, evadir detecciones básicas mediante retrasos aleatorios y consolidar la información en formatos estructurados.

---

## ✨ Características Principales

- **Navegación Asíncrona:** Basado en `playwright` para una ejecución rápida y eficiente.
- **Extracción desde el listado:** Captura título, empresa y resumen de cada oferta directamente desde las cards del listado (sin visitar cada oferta).
- **Evasión de Bloqueos:** Implementa retrasos aleatorios con distribución uniforme para mimetizar el comportamiento humano.
- **Gestión de Datos:** 
  - Guarda el contenido de cada oferta en archivos `.txt` individuales.
  - Genera un resumen maestro en Excel (`.xlsx`) con fecha y URL.
- **Detección de Duplicados:** Mantiene un Excel maestro con historial de 30 días; las ofertas ya vistas no se vuelven a procesar.
- **Análisis por Puntaje:** Cada oferta se puntúa según keywords de perfil data/automatización y se marcan flags (remoto, híbrido, inglés, part-time, práctica, trainee).
- **Ejecución Automática:** Workflow de GitHub Actions que corre el scraper a diario y commitea los resultados en `data/`.

---

## 🛠️ Requisitos

- **Python:** 3.12+
- **Dependencias:** Listadas en `requirements.txt` (Playwright, Pandas, BeautifulSoup4, openpyxl, etc.)

---

## 🚀 Instalación y Configuración

1. **Clonar el repositorio o descargar los archivos.**
2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Instalar los navegadores de Playwright:**
   ```bash
   playwright install chromium
   ```

---

## ⚙️ Uso (Línea de Comandos)

El script se ejecuta desde `main.py` y acepta los siguientes argumentos:

| Argumento | Descripción | Por Defecto |
| :--- | :--- | :--- |
| `--dir` | Directorio raíz donde se guardarán los resultados. | `data` |
| `--headless` | `true` para ejecutar sin ventana, `false` para ver el navegador. | `false` |
| `--pages` | Cantidad máxima de páginas a recorrer (0 para todas). | `0` (Todas) |
| `--delay` | Tiempo promedio de espera (segundos) entre páginas. | `3.0` |

### Ejemplo de ejecución:
```bash
python main.py --dir "C:\Proyectos\ScraperLaborum\Data" --headless false --pages 5 --delay 2.5
```

---

## 📁 Estructura del Proyecto

```text
laborum_scraper/
├── main.py          # Punto de entrada y orquestación del flujo.
├── scraper.py       # Lógica de extracción y procesamiento de páginas.
├── browser.py       # Configuración y ciclo de vida del navegador (Playwright).
├── config.py        # Configuración global (URLs, reintentos).
├── utils.py         # Funciones auxiliares (logs, limpieza de texto, decoradores).
├── requirements.txt # Librerías necesarias.
└── README.md        # Documentación del proyecto.
```

---

## 📊 Salida de Datos (Output)

Los archivos se organizan automáticamente por fecha en la carpeta indicada en `--dir`:

1. **Raw Data (`/laborum/raw_data/YYYY-MM-DD/*.txt`):** 
   - Un archivo por cada oferta, nombrado como titulo_sanitizado_idOferta.txt (el id evita colisiones entre títulos repetidos).
   - Contiene la descripción completa o resumen de la vacante.
2. **Summary Data (`/laborum/summary_data.xlsx`):**
   - Excel maestro consolidado (historial rodante de 30 días) con columnas: `Fecha`, `Nombre`, `Empresa`, `Ubicacion`, `Tipo`, `Pageweb`, `puntaje_data`, `keyword`, `ingles`, `remoto`, `hibrido`, `presencial`, `part_time`, `practica`, `trainee`, `automatizacion`, `oferta`.

---

## 🧠 Arquitectura Técnica

El scraper sigue un ciclo de vida robusto:
1. **Inicio:** Configura el navegador y verifica datos previos para evitar duplicados.
2. **Navegación:** Accede a la URL de Laborum y cierra automáticamente modales publicitarios.
3. **Extracción:** Recorre el listado, captura los datos visibles y guarda archivos individuales.
4. **Paginación:** Busca el botón "Siguiente", aplica un retraso aleatorio y repite el proceso.
5. **Cierre:** Consolida la lista final en un reporte Excel.

---

## ⚠️ Notas Legales
Este proyecto tiene fines educativos. El uso de herramientas de web scraping debe respetar los términos y condiciones del sitio web (`laborum.cl/robots.txt`) y la legislación vigente sobre protección de datos.
