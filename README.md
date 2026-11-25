# ControlVest

Sistema de control del código de vestimenta institucional en tiempo real. La clasificación de la vestimenta y el reconocimiento facial se ejecutan en el navegador con TensorFlow.js y face-api.js. El backend solo recibe datos cuando se confirma una infracción, por lo que el video nunca sale del equipo del laboratorio.

## Integrantes

| Integrante | Responsabilidad |
|---|---|
| Ruth Estafni Huillca | Estructura del proyecto y entrenamiento del modelo de vestimenta |
| Valeria Tasayco | Desarrollo del backend (API FastAPI y base de datos SQLite) |
| Richard Cornejo | Desarrollo del frontend (interfaz, cámara y lógica de detección) |

## Funcionamiento

1. La webcam alimenta un `<video>` y cada fotograma se dibuja en un `<canvas>`.
2. El modelo de Teachable Machine clasifica la vestimenta en cuatro clases: `Cumple_Formal`, `Cumple_Verano`, `Incumplimiento` y `Sin_Alumno`.
3. Si la clase de infracción supera el 85% de confianza durante 3 segundos continuos, se confirma la infracción.
4. face-api.js identifica al alumno comparando su rostro con los descriptores registrados.
5. El frontend envía `POST /api/infracciones` al backend. Si el mismo alumno ya tiene un registro en los últimos 30 segundos, el servidor responde `429` y no duplica el registro.
6. El historial se muestra en una tabla y se puede exportar a CSV.

## Estructura del proyecto

```
ControlVest/
├── frontend/
│   ├── index.html                 # Interfaz principal
│   ├── enrolar.html               # Registro de rostros de los alumnos
│   ├── css/styles.css
│   ├── js/
│   │   ├── app.js                 # Cámara, TF.js, regla de estabilidad y envío al backend
│   │   └── face_auth.js           # Identificación facial con face-api.js
│   └── model/
│       ├── Vestimentas/           # model.json, metadata.json, weights.bin (Teachable Machine)
│       └── Rostros/
│           └── descriptores.json  # Generado con enrolar.html
├── backend/
│   ├── main.py                    # API FastAPI
│   ├── database.py                # Conexión y tabla SQLite
│   └── control_vestimenta.db      # Se crea automáticamente al iniciar
└── docs/
    └── Informe_Tecnico_ControlVest.pdf
```

## Requisitos

- Python 3.10 o superior
- Un navegador moderno (Chrome o Edge recomendados)
- Conexión a internet la primera vez, para cargar TensorFlow.js, Teachable Machine y face-api.js desde CDN
- Una webcam disponible y sin otra aplicación usándola

## Instalación y ejecución

### 1. Backend

Desde la carpeta `ControlVest/backend`:

```powershell
python -m pip install fastapi uvicorn
python -m uvicorn main:app --reload
```

El servidor queda en `http://localhost:8000`. Verifica que responde en `http://localhost:8000/` y que la documentación interactiva funciona en `http://localhost:8000/docs`.

### 2. Frontend

En una segunda terminal, desde la carpeta `ControlVest/frontend`:

```powershell
python -m http.server 5500
```

Abre `http://localhost:5500` en el navegador.

> No abras `index.html` con doble clic. Los modelos no cargan desde `file://`, así que siempre debes usar el servidor local.

### 3. Registrar a los alumnos

El reconocimiento facial necesita los descriptores de cada integrante antes de usarse.

1. Cierra `index.html` en todas las pestañas para liberar la cámara.
2. Abre `http://localhost:5500/enrolar.html`.
3. Escribe el nombre de la persona, por ejemplo `Ruth Estafni Huillca`, y pulsa **Capturar 15 muestras**. Mueve un poco la cabeza durante la captura.
4. Repite el paso con cada alumno. Para mejores resultados, captura en dos sesiones con distinta iluminación.
5. Pulsa **Descargar descriptores.json** y guárdalo en `frontend/model/Rostros/`, reemplazando el anterior.
6. Vuelve a `index.html` y recarga con `Ctrl + F5`.

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Estado del servicio y cooldown configurado |
| `POST` | `/api/infracciones` | Registra una infracción |
| `GET` | `/api/infracciones?limit=200` | Lista las infracciones más recientes |

Ejemplo de cuerpo para `POST /api/infracciones`:

```json
{
  "nombre_alumno": "Alumno_Pruba",
  "estado_detectado": "Incumplimiento_Vestimenta",
  "confianza": 91.5,
  "fecha_hora": "2026-11-25T21:07:49Z"
}
```

Códigos de respuesta:

- `201`: infracción registrada.
- `429`: cooldown activo para ese alumno. El cuerpo indica los segundos restantes.
- `422`: datos inválidos, por ejemplo una confianza fuera de 0 a 100.

El campo `fecha_hora` es opcional. Si no se envía, el servidor usa su hora actual.

## Parámetros de configuración

| Parámetro | Archivo | Valor | Función |
|---|---|---|---|
| `COOLDOWN_SECONDS` | `backend/database.py` | `30` | Tiempo mínimo entre registros del mismo alumno |
| `UMBRAL_INFRACCION` | `frontend/js/app.js` | `0.85` | Confianza mínima para contar una infracción |
| `DURACION_CONFIRMACION_MS` | `frontend/js/app.js` | `3000` | Tiempo continuo requerido para confirmar |
| `INTERVALO_ROSTRO_MS` | `frontend/js/app.js` | `400` | Frecuencia del reconocimiento facial |
| `FACE_CONFIDENCE_THRESHOLD` | `frontend/js/face_auth.js` | `0.6` | Similitud mínima para asignar un nombre |
| `MARGEN_MINIMO` | `frontend/js/face_auth.js` | `0.05` | Diferencia mínima entre los dos mejores candidatos |

Si el sistema confunde a dos personas, sube `MARGEN_MINIMO` o `FACE_CONFIDENCE_THRESHOLD`. Si no reconoce a una persona registrada, baja el umbral o agrega más muestras con la misma iluminación del laboratorio.

## Solución de problemas

**`Could not import module "main"`**
Uvicorn se ejecutó fuera de la carpeta `backend`. Entra con `cd ControlVest\backend` y vuelve a ejecutar el comando.

**`sqlite3.OperationalError: no such column: created_at_epoch`**
La base de datos es de una versión anterior. Detén el servidor, borra `backend/control_vestimenta.db` y vuelve a iniciarlo. Se creará con la estructura correcta.

**`Vestimentas: Error` en la pastilla superior**
Revisa `frontend/model/Vestimentas/metadata.json`. El mensaje de la barra de alerta indica qué clase falta.

**`No se pudo iniciar la cámara: Device in use`**
Otra aplicación o pestaña está usando la webcam. Cierra Teams, Zoom, Meet o cualquier otra pestaña con la cámara activa, o reinicia el navegador.

**`Backend: Offline`**
El servidor de FastAPI no está corriendo, o la URL en la caja de ajustes no coincide con `http://localhost:8000`. Las infracciones se guardan temporalmente en memoria hasta que el backend vuelva a estar disponible.

**Todas las personas aparecen como `Alumno No Registrado`**
Falta generar `descriptores.json` con `enrolar.html`, o el archivo no contiene a la persona que está frente a la cámara.

## Limitaciones conocidas

- El cooldown se aplica por nombre. Todas las personas no registradas comparten el mismo cooldown.
- La iluminación del laboratorio y el encuadre parcial del pantalón afectan la confianza del modelo de vestimenta.
- El modelo de vestimenta recibido usa la etiqueta `Incumplimiento`. El código la traduce a `Incumplimiento_Vestimenta` al guardar el registro.
- Los descriptores faciales son datos biométricos. Deben guardarse solo con el consentimiento de cada alumno y con acceso restringido.
- Las infracciones deben revisarse por una persona antes de aplicar cualquier sanción.

## Tecnologías

- **Frontend:** HTML5, CSS3, JavaScript (ES Modules), TensorFlow.js 4.20, Teachable Machine Image 0.8.5, face-api.js 1.7.13
- **Backend:** Python, FastAPI, Uvicorn, SQLite
- **Modelos:** Transfer learning con MobileNet (Teachable Machine) para vestimenta; embeddings faciales de 128 dimensiones (face-api.js) para identidad
