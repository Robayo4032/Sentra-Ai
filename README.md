# 🧠 Sentra AI — Asistente de Inteligencia Artificial Local con Interfaz HUD Holográfica

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/LLM-Ollama%20%7C%20Llama3.1-green" />
  <img src="https://img.shields.io/badge/UI-Tkinter%20HUD-cyan" />
  <img src="https://img.shields.io/badge/Voz-Edge--TTS%20Neuronal-orange" />
  <img src="https://img.shields.io/badge/Acceso-Móvil%20QR-purple" />
  <img src="https://img.shields.io/badge/Licencia-MIT-lightgrey" />
</p>

---

## ¿Qué es Sentra AI?

**Sentra AI** es un asistente de inteligencia artificial **completamente local** (sin depender de la nube) con una interfaz visual HUD inspirada en los sistemas de **Stark Industries** (Iron Man). Funciona con modelos de lenguaje ejecutados en tu propia máquina a través de **Ollama**, lo que garantiza privacidad total de tus datos.

### Características principales

| Característica | Descripción |
|---|---|
| 🤖 **IA Local** | Ejecuta modelos LLM (Llama 3.1, Gemma, Mistral, etc.) en tu PC con Ollama. Sin enviar datos a la nube. |
| 🎨 **HUD Holográfico** | Interfaz visual con reactor Arc animado, pistas de circuito de cobre, engranajes giratorios, iris segmentado y orbe 3D. |
| 🗣️ **Voz Neuronal** | Respuestas con voz en español mediante Edge-TTS (Microsoft Neural TTS) con fallback a System.Speech. |
| 👂 **Escucha Continua** | Reconocimiento de voz local con Faster-Whisper. Di el nombre del asistente y tu orden. |
| 📱 **Acceso Móvil** | Escanea un código QR desde tu celular para enviar consultas desde cualquier dispositivo en tu red local. |
| 🧠 **Memoria Persistente** | Recuerda datos sobre ti entre sesiones: «recuerda que me llamo Ana», «¿qué sabes de mí?». |
| 🎨 **Color Personalizable** | Cambia el color del tema completo del HUD en tiempo real. |
| ⚡ **Acciones del Sistema** | Abre apps, busca en YouTube, controla volumen, apaga el PC, crea archivos, y más. |
| 📷 **Análisis de Imágenes** | Describe y analiza imágenes usando modelos de visión (LLaVA). |
| 🔐 **100% Privado** | Todo se ejecuta localmente. Tus conversaciones y memoria nunca salen de tu máquina. |

---

## 📋 Requisitos

### Software necesario

1. **Python 3.10+** → [python.org](https://www.python.org/downloads/)
2. **Ollama** → [ollama.com](https://ollama.com/download) (para ejecutar modelos LLM localmente)

### Modelo de IA

Después de instalar Ollama, descarga el modelo ejecutando en tu terminal:

```bash
ollama pull llama3.1
```

Para análisis de imágenes (opcional):

```bash
ollama pull llava
```

### Dependencias de Python

```bash
pip install edge-tts psutil
```

**Opcionales** (para funciones avanzadas):

```bash
# Reconocimiento de voz local
pip install sounddevice numpy faster-whisper

# Si usas sentra_ai.py con API de Google (alternativa a Ollama)
pip install google-generativeai
```

---

## 🚀 Instalación y Uso

### 1. Clona el repositorio

```bash
git clone https://github.com/Robayo4032/sentra-ai.git
cd sentra-ai
```

### 2. Configura

Copia el archivo de configuración de ejemplo:

```bash
cp config.example.json config.json
```

Edita `config.json` con tus preferencias:

```json
{
  "nombre": "Sentra Ai",
  "modelo": "llama3.1",
  "vision": "llava",
  "whisper": "base",
  "mic": 1,
  "voz": "",
  "puerto": 8765,
  "carpeta_git": ""
}
```

| Campo | Descripción |
|---|---|
| `nombre` | Nombre que el asistente usa para identificarse y que tú dices para activarlo por voz. |
| `modelo` | Modelo LLM de Ollama a usar (e.g. `llama3.1`, `gemma2`, `mistral`). |
| `vision` | Modelo de visión para analizar imágenes (e.g. `llava`). |
| `whisper` | Tamaño del modelo Whisper para STT: `tiny`, `base`, `small`, `medium`. |
| `mic` | Índice del micrófono a usar (puedes verlos en la app con el botón MICRÓFONO). |
| `voz` | Voz de Edge-TTS (vacío = auto-selecciona español). |
| `puerto` | Puerto del servidor móvil para acceso desde el celular. |

### 3. (Opcional) API Key

Si usas `sentra_ai.py` con la API de Grok/Gemini en lugar de Ollama, crea un archivo `api_key.txt` en la misma carpeta y pega tu clave:

```
tu-api-key-aqui
```

> ⚠️ **Nunca compartas ni subas tu `api_key.txt` a GitHub.** Ya está incluido en `.gitignore`.

### 4. Ejecuta

**Versión principal con interfaz HUD (recomendada):**

```bash
python sentra_ai_gui.py
```

**Versión alternativa con interfaz web (navegador):**

```bash
python sentra_ai.py
```

---

## 🖥️ Estructura del Proyecto

```
sentra-ai/
├── sentra_ai_gui.py       # 🎯 App principal: HUD de escritorio con Tkinter
├── sentra_ai.py           # Versión alternativa con interfaz web (navegador)
├── voz_sentra_ai.py       # Motor de voz neuronal (Edge-TTS + fallback)
├── ollama.py              # Cliente para API de LLM (Ollama / Grok / Gemini)
├── gui_part.py            # Componentes auxiliares de GUI
├── fusionar.py            # Utilidad para fusionar archivos de código
├── hud.html               # Interfaz web HUD para sentra_ai.py
├── config.example.json    # Plantilla de configuración (copiar a config.json)
├── .gitignore             # Archivos excluidos de Git
└── README.md              # Este archivo
```

### Archivos generados en ejecución (no incluidos en el repo)

| Archivo | Contenido |
|---|---|
| `config.json` | Tu configuración personal |
| `api_key.txt` | Tu API key (si usas API externa) |
| `memoria.json` | Memoria persistente del asistente |
| `tareas.json` | Tareas programadas |
| `voz_sentra_ai.json` | Cache de configuración de voz |

---

## 🎮 Comandos y Uso

### Por texto (en la barra de entrada)

| Comando | Ejemplo |
|---|---|
| Preguntas generales | *«¿Qué es la energía solar?»* |
| Abrir aplicaciones | *«abre YouTube»*, *«abre la calculadora»* |
| Buscar en YouTube | *«busca en YouTube música lo-fi»* |
| Control de volumen | *«sube el volumen»*, *«baja el volumen»*, *«silencio»* |
| Guardar memorias | *«recuerda que me llamo Derek»* |
| Consultar memorias | *«¿qué sabes de mí?»* |
| Olvidar todo | *«olvida todo»* |
| Deshacer | *«deshaz eso»* |
| Estado del sistema | *«estado de mi PC»* |
| Crear archivos | *«crea un archivo llamado notas.txt»* |
| Modo Iron Man | *«modo Iron Man»* (cambia personalidad a EDITH) |
| Cambiar color | *«cambia el color a rojo»* |
| Apagar PC | *«apaga el computador»* (requiere confirmación) |

### Por voz

1. Pulsa el botón **HABLAR** o presiona `Ctrl + Espacio`.
2. Activa **ESCUCHA** para modo continuo: di *«Sentra»* seguido de tu orden.

### Acceso desde el celular 📱

1. Pulsa el botón **📱 CELULAR** en el HUD.
2. Escanea el código QR con la cámara de tu teléfono.
3. Se abrirá una interfaz web donde puedes escribir consultas que se procesan en tu PC.

---

## 🎨 Interfaz HUD

La interfaz está inspirada en la tecnología de Stark Industries e incluye:

- **Pistas de circuito de cobre** (PCB traces) con ángulos a 45° y vías de soldadura
- **Reactor Arc holográfico** con múltiples anillos animados:
  - Anillo graduado de medición con ticks giratorios
  - Engranaje dentado de 40 dientes
  - Arco rojo de estado (10:00 a 12:00)
  - Pistas cyan segmentadas giratorias
  - Iris mecánico de 3 aspas
  - Orbe esférico 3D con brillo especular
- **Marco contenedor** con soportes de esquina cyan y marcas perimetrales
- **Telemetría en vivo**: CPU, RAM, volumen, reloj digital
- **Indicador de estado** dinámico: EN LÍNEA, ESCUCHANDO, PROCESANDO, TRANSMITIENDO
- **Feed de comunicaciones** con historial de conversación completo
- **Botones de acción** organizados en cápsulas con código de color

---

## 🛠️ Tecnologías

- **Python 3** — Lenguaje principal
- **Tkinter** — Interfaz gráfica de escritorio
- **Ollama** — Ejecución local de modelos LLM
- **Edge-TTS** — Síntesis de voz neuronal de Microsoft
- **Faster-Whisper** — Reconocimiento de voz local (STT)
- **psutil** — Monitoreo de sistema en tiempo real

---

## 📄 Licencia

Este proyecto es de código abierto bajo la licencia **MIT**. Puedes usarlo, modificarlo y distribuirlo libremente.

---

<p align="center">
  <b>Creado por Derek 🧠⚡</b><br>
  <i>«La tecnología más avanzada es la que sirve a las personas.»</i>
</p>
