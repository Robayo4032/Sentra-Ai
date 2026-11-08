# 🤖 Sentra AI

Este es el proyecto de Sentra AI, un asistente inteligente desarrollado en Python.

## 🚀 Características
- Interfaz gráfica intuitiva.
- Integración con modelos de lenguaje (Ollama/AI).
- Sistema de voz avanzado.
- Gestión de memoria y configuración personalizable.

## 🛠️ Instalación y Configuración

Para ejecutar este proyecto en tu máquina local, sigue estos pasos:

### 1. Clonar el repositorio
```bash
git clone https://github.com/TU_USUARIO/TU_REPOSITORIO.git
cd Jarvis-AI
```

### 2. Crear un entorno virtual e instalar dependencias
```bash
python -m venv venv
# Activar entorno:
# Windows: .\venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuración de Claves (IMPORTANTE) 🔑
Por razones de seguridad, las claves de API y archivos de configuración no se suben al repositorio. Debes crear los siguientes archivos en la raíz del proyecto:

- **`api_key.txt`**: Crea este archivo y pega tu clave de API dentro.
- **`config.json`**: Crea este archivo con la configuración necesaria para el sistema.

## 📂 Estructura del Proyecto
- `sentra_ai.py`: Lógica principal del cerebro de la IA.
- `sentra_ai_gui.py`: Interfaz gráfica de usuario.
- `ollama.py`: Integración con Ollama.
- `voz_sentra_ai.py`: Sistema de procesamiento de voz.
- `gui_part.py`: Componentes visuales adicionales.

---
Desarrollado por Derek.
