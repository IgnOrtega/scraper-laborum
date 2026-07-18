# Laborum Scraper 🚀

Scraper automatizado desarrollado con **Python** y **Requests** para la extracción masiva de ofertas laborales desde el portal **Laborum.cl**.

En lugar de renderizar la página con un navegador, el scraper consume directamente la **API interna del sitio** (la misma que usa el frontend), lo que lo hace rápido, liviano y apto para correr en GitHub Actions.

---

## ✨ Características Principales

- **Consumo directo de la API:** Obtiene las ofertas en JSON (título, empresa, ubicación, tipo, modalidad y **descripción completa**), sin navegador ni parsing de HTML.
- **Filtro de fecha automático:** El filtro de publicación (hoy, menor a 2 días, 1 semana, 1 mes, …) se deriva del slug de `BASE_URL` en `config.py`.
- **Evasión de Bloqueos:** Sesión con cookies del sitio y retrasos aleatorios con distribución uniforme entre páginas.
- **Gestión de Datos:**
  - Guarda el contenido de cada oferta en archivos `.txt` individuales.
  - Genera un Excel maestro con historial rodante de 30 días.
- **Detección de Duplicados:** Las ofertas ya vistas (por id) no se vuelven a procesar.
- **Análisis por Puntaje:** Cada oferta se puntúa según keywords de perfil data/automatización y se marcan flags (remoto, híbrido, inglés, part-time, práctica, trainee).
- **Ejecución Automática:** Workflow de GitHub Actions que corre el scraper a diario y commitea los resultados en `data/`.

---

## 🛠️ Requisitos

- **Python:** 3.12+
- **Dependencias:** Listadas en `requirements.txt` (Requests, Pandas, openpyxl, etc.)

---

## 🚀 Instalación y Configuración

1. **Clonar el repositorio o descargar los archivos.**
2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚙️ Uso (Línea de Comandos)

El script se ejecuta desde `main.py` y acepta los siguientes argumentos:

| Argumento | Descripción | Por Defecto |
| :--- | :--- | :--- |
| `--dir` | Directorio raíz donde se guardarán los resultados. | `data` |
| `--pages` | Cantidad máxima de páginas a recorrer (0 para todas; 50 ofertas por página). | `0` (Todas) |
| `--delay` | Tiempo promedio de espera (segundos) entre páginas. | `3.0` |

### Ejemplo de ejecución:
```bash
python main.py --dir data --pages 5 --delay 2.5
```

Para cambiar la ventana de ofertas (hoy / 2 días / 1 semana / 1 mes), edita `BASE_URL` en `config.py` — el filtro de la API se deriva automáticamente del enlace.

---

## 📁 Estructura del Proyecto

```text
laborum_scraper/
├── main.py              # Punto de entrada y orquestación del flujo.
├── scraper.py           # Cliente de la API y procesamiento de ofertas.
├── processor_utils.py   # Análisis por puntaje/keywords y flags de modalidad.
├── config.py            # Configuración global (URL del listado, fecha).
├── utils.py             # Funciones auxiliares (logs, historial, limpieza).
├── requirements.txt     # Librerías necesarias.
└── readme.md            # Documentación del proyecto.
```

---

## 📊 Salida de Datos (Output)

Los archivos se organizan automáticamente en la carpeta indicada en `--dir` (en GitHub Actions: `data/` en la raíz del repo):

1. **Raw Data (`/laborum/raw_data/YYYY-MM-DD/*.txt`):**
   - Un archivo por cada oferta, nombrado como `titulo_sanitizado_idOferta.txt`.
   - Contiene URL, empresa, ubicación, tipo y la descripción completa de la vacante.
2. **Summary Data (`/laborum/summary_data.xlsx`):**
   - Excel maestro consolidado (historial rodante de 30 días) con columnas: `Fecha`, `Nombre`, `Empresa`, `Ubicacion`, `Tipo`, `Pageweb`, `puntaje_data`, `keyword`, `ingles`, `remoto`, `hibrido`, `presencial`, `part_time`, `practica`, `trainee`, `automatizacion`, `oferta`.

Las carpetas de `raw_data` y las filas del Excel con más de 30 días se eliminan automáticamente en cada corrida.

---

## 🧠 Arquitectura Técnica

El scraper sigue este ciclo de vida:
1. **Inicio:** Limpia datos antiguos y carga el historial del Excel maestro (ids ya vistos).
2. **Sesión:** Visita la página del listado para obtener las cookies que exige la API.
3. **Extracción:** Recorre la API página a página (50 ofertas por página), analiza cada oferta nueva y guarda su `.txt`.
4. **Paginación:** Aplica un retraso aleatorio entre páginas hasta agotar el total reportado por la API.
5. **Cierre:** Consolida historial + ofertas nuevas en el Excel maestro (también se guarda incrementalmente cada 5 páginas).

---

## ⚠️ Notas Legales
Este proyecto tiene fines educativos. El uso de herramientas de web scraping debe respetar los términos y condiciones del sitio web (`laborum.cl/robots.txt`) y la legislación vigente sobre protección de datos.
