from datetime import date

#BASE_URL = "https://firstjob.me/ofertas?semantic=a&type%5B%5D=1"
#BASE_URL= "https://www.laborum.cl/empleos-publicacion-menor-a-1-mes.html?recientes=true"
#BASE_URL=  "https://www.laborum.cl/empleos-publicacion-menor-a-3-dias.html?recientes=true"
BASE_URL= r"https://www.laborum.cl/empleos-publicacion-menor-a-7-dias.html?recientes=true"
FECHA_HOY = date.today().isoformat()

# Configuration
MAX_RETRIES = 3
MAX_CONCURRENT_REQUESTS = 5
RETRY_DELAY = 1.0
