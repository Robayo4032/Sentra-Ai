#!/usr/bin/env python3
"""
Sentra Ai · asistente local con interfaz HUD.
Creado por Derek · github.com/DerekAI
Uso:  python sentra_ai.py
"""
import os, sys, json, time, ast, re, base64, secrets, threading, subprocess, webbrowser, datetime, operator, ctypes, unicodedata, collections
import urllib.request, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
try: import google.generativeai as genai
except ImportError: genai = None

def _imp(n):
    try: return __import__(n)
    except Exception: return None
ollama, psutil, sd, np = _imp('ollama'), _imp('psutil'), _imp('sounddevice'), _imp('numpy')
try: from faster_whisper import WhisperModel
except Exception: WhisperModel = None

try: import voz_sentra_ai
except Exception: voz_sentra_ai = None

AQUI = os.path.dirname(os.path.abspath(__file__)); P = lambda f: os.path.join(AQUI, f)
HOME = os.path.expanduser('~')
CFG = {'nombre': 'Sentra Ai', 'modelo': 'llama3.1', 'vision': 'llava', 'whisper': 'small', 'mic': None, 'voz': '', 'puerto': 8765, 'color': '#00e5ff', 'carpeta_git': ''}
def cargar(f, d):
    try: return json.load(open(P(f), encoding='utf-8'))
    except Exception: return d
def guardar(f, v): json.dump(v, open(P(f), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
CFG.update(cargar('config.json', {})); MEM = cargar('memoria.json', []); TAREAS = cargar('tareas.json', [])
TOKEN = secrets.token_urlsafe(16)
S = {'estado': 'listo', 'nombre': CFG['nombre'], 'color': CFG['color'], 'voz': True, 'escucha': False, 'una': False, 'activo': 0, 'pendiente': None, 'vol': 50, 'mudo': False}
EV, UNDO, HIST, TURNO = [], [], [], threading.Lock()
def ev(q, t): EV.append({'id': len(EV) + 1, 'q': q, 't': t})
def norm(s): return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn').strip()

# ---------- voz de salida (neuronal con fallback a PowerShell/System.Speech) ----------
PS = ("Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
      "$c=New-Object Globalization.CultureInfo 'es-ES';if($env:JVOZ){try{$s.SelectVoice($env:JVOZ)}catch{}}"
      "else{try{$s.SelectVoiceByHints('Male','NotSet',0,$c)}catch{try{$s.SelectVoiceByHints('NotSet','NotSet',0,$c)}catch{}}};$s.Speak($env:JTXT)")
_tts = None
def callar():
    global _tts
    if voz_sentra_ai:
        try: voz_sentra_ai.callar()
        except Exception: pass
    if _tts and _tts.poll() is None: _tts.kill()

def hablar(t):
    global _tts
    callar()
    if not S['voz'] or sys.platform != 'win32': return
    S['estado'] = 'hablando'
    if voz_sentra_ai:
        try:
            voz_sentra_ai.hablar(t)
            if S['estado'] == 'hablando': S['estado'] = 'listo'
            return
        except Exception:
            pass
    _tts = subprocess.Popen(['powershell', '-NoProfile', '-Command', PS], env=dict(os.environ, JTXT=t, JVOZ=CFG['voz']), creationflags=0x08000000)
    _tts.wait()
    if S['estado'] == 'hablando': S['estado'] = 'listo'
def anunciar(t): ev('sentra ai', t); threading.Thread(target=hablar, args=(t,), daemon=True).start()

# ---------- herramientas (el modelo decide cuándo usarlas) ----------
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
SITIOS = {'youtube': 'youtube.com', 'google': 'google.com', 'gmail': 'mail.google.com', 'whatsapp': 'web.whatsapp.com', 'spotify': 'open.spotify.com', 'netflix': 'netflix.com', 'github': 'github.com', 'mapas': 'google.com/maps', 'instagram': 'instagram.com', 'linkedin': 'linkedin.com', 'x': 'x.com'}
APPS = {'calculadora': 'calc', 'bloc de notas': 'notepad', 'paint': 'mspaint', 'explorador': 'explorer', 'administrador de tareas': 'taskmgr', 'chrome': 'chrome', 'edge': 'msedge', 'spotify': 'spotify', 'word': 'winword', 'excel': 'excel', 'powerpoint': 'powerpnt', 'configuracion': 'ms-settings:'}
COLORES = {'rojo': '#ff3b30', 'azul': '#3b82f6', 'verde': '#22e07a', 'naranja': '#ff9500', 'morado': '#a855f7', 'rosa': '#ff5fa2', 'amarillo': '#ffd60a', 'cian': '#00e5ff', 'dorado': '#ffb300'}
WMO = {0: 'despejado', 1: 'mayormente despejado', 2: 'parcialmente nublado', 3: 'nublado', 45: 'con niebla', 61: 'con lluvia ligera', 63: 'con lluvia', 65: 'con lluvia fuerte', 80: 'con chubascos', 95: 'con tormenta'}

def web(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'SentraAi-local/1.0'}), timeout=6).read())
def pedir(desc, fn):
    S['pendiente'] = (desc, fn); return f'Acción pendiente: el usuario debe confirmarla en pantalla ({desc}).'

def hora() -> str:
    """Devuelve la hora actual."""
    return datetime.datetime.now().strftime('%H:%M')
def fecha() -> str:
    """Devuelve la fecha de hoy."""
    d = datetime.date.today(); return f'{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}'
def estado_pc() -> str:
    """Estado del PC: CPU, RAM, batería y disco."""
    if not psutil: return 'Falta instalar psutil.'
    b = psutil.sensors_battery(); return f'CPU {psutil.cpu_percent()} %, RAM {psutil.virtual_memory().percent} %, disco {psutil.disk_usage(HOME).percent} %' + (f', batería {round(b.percent)} %' if b else '')
def _vol(a):
    k = {'subir': 0xAF, 'bajar': 0xAE, 'silenciar': 0xAD}[a]
    for _ in range(1 if a == 'silenciar' else 5): ctypes.windll.user32.keybd_event(k, 0, 0, 0); ctypes.windll.user32.keybd_event(k, 0, 2, 0)
    if a == 'silenciar': S['mudo'] = not S['mudo']
    else: S['vol'] = max(0, min(100, S['vol'] + (10 if a == 'subir' else -10)))
def volumen(accion: str) -> str:
    """Sube, baja o silencia el volumen del PC.
    Args:
        accion: 'subir', 'bajar' o 'silenciar'
    """
    a = norm(accion)
    if a not in ('subir', 'bajar', 'silenciar') or sys.platform != 'win32': return 'No puedo hacer eso.'
    _vol(a); UNDO.append(('volumen ' + a, lambda: _vol({'subir': 'bajar', 'bajar': 'subir', 'silenciar': 'silenciar'}[a]))); return 'Hecho.'
def abrir_web(destino: str, busqueda: str = '') -> str:
    """Abre un sitio web o busca algo en YouTube/Google.
    Args:
        destino: nombre del sitio (youtube, google, gmail...) o dominio
        busqueda: texto a buscar (opcional)
    """
    d = norm(destino); host = SITIOS.get(d) or (d if re.fullmatch(r'[\w.-]+\.[a-z]{2,}(/\S*)?', d) else None)
    if busqueda: url = ('https://www.youtube.com/results?search_query=' if d == 'youtube' else 'https://www.google.com/search?q=') + urllib.parse.quote(busqueda)
    elif host: url = 'https://' + host
    else: url = 'https://www.google.com/search?q=' + urllib.parse.quote(destino)
    webbrowser.open(url); return 'Abierto ' + url
def abrir_app(nombre: str) -> str:
    """Abre una aplicación del PC (calculadora, bloc de notas, paint, chrome, spotify, word, excel...).
    Args:
        nombre: nombre de la aplicación
    """
    c = APPS.get(norm(nombre))
    if not c: return 'App no permitida. Disponibles: ' + ', '.join(APPS)
    subprocess.Popen(f'start "" "{c}"', shell=True); return 'Abierta.'
def clima(ciudad: str) -> str:
    """Clima actual de una ciudad.
    Args:
        ciudad: nombre de la ciudad
    """
    g = web('https://geocoding-api.open-meteo.com/v1/search?count=1&language=es&name=' + urllib.parse.quote(ciudad))
    if not g.get('results'): return 'Ciudad no encontrada.'
    l = g['results'][0]; w = web(f"https://api.open-meteo.com/v1/forecast?latitude={l['latitude']}&longitude={l['longitude']}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m")['current']
    return f"{l['name']}: {round(w['temperature_2m'])} °C (sensación {round(w['apparent_temperature'])} °C), {WMO.get(w['weather_code'], 'variable')}, viento {round(w['wind_speed_10m'])} km/h"
def buscar_info(tema: str) -> str:
    """Busca información en Wikipedia sobre un tema.
    Args:
        tema: tema a investigar
    """
    h = web('https://es.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=1&srsearch=' + urllib.parse.quote(tema))['query']['search']
    if not h: return 'Sin resultados.'
    return (web('https://es.wikipedia.org/api/rest_v1/page/summary/' + urllib.parse.quote(h[0]['title'].replace(' ', '_'))).get('extract') or 'Sin resumen.')[:600]
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod, ast.USub: operator.neg}
def _ev(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in OPS:
        a, b = _ev(n.left), _ev(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 100: raise ValueError('exponente demasiado grande')
        return OPS[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and type(n.op) in OPS: return OPS[type(n.op)](_ev(n.operand))
    raise ValueError('expresión no válida')
def calcular(expresion: str) -> str:
    """Calcula una expresión matemática.
    Args:
        expresion: por ejemplo '25*4+10' o '0.15*200'
    """
    return str(round(_ev(ast.parse(expresion.replace('^', '**').replace(',', '.'), mode='eval').body), 6))
def nota(texto: str) -> str:
    """Guarda una nota de texto en Documentos.
    Args:
        texto: contenido de la nota
    """
    d = os.path.join(HOME, 'Documents', 'Sentra Ai notas'); os.makedirs(d, exist_ok=True)
    f = os.path.join(d, datetime.datetime.now().strftime('nota_%Y%m%d_%H%M%S.txt')); open(f, 'w', encoding='utf-8').write(texto)
    UNDO.append(('nota', lambda: os.remove(f))); return 'Nota guardada en ' + f
def recordar(dato: str) -> str:
    """Recuerda un dato sobre el usuario (nombre, gustos, etc.).
    Args:
        dato: frase corta, por ejemplo 'Se llama Ana'
    """
    if dato not in MEM: MEM.append(dato); guardar('memoria.json', MEM)
    return 'Recordado.'
def olvidar(texto: str) -> str:
    """Olvida datos del usuario que contengan el texto, o todo si el texto es 'todo'.
    Args:
        texto: palabra a olvidar o 'todo'
    """
    t = norm(texto); n = len(MEM); MEM[:] = [m for m in MEM if t != 'todo' and t not in norm(m)]; guardar('memoria.json', MEM); return f'{n - len(MEM)} borrado(s).'
def lista(accion: str, texto: str = '') -> str:
    """Lista de tareas del usuario.
    Args:
        accion: 'agregar', 'ver' o 'vaciar'
        texto: tarea a agregar
    """
    a = norm(accion)
    if a.startswith('agreg'): TAREAS.append(texto); guardar('tareas.json', TAREAS); UNDO.append(('tarea', lambda: (TAREAS.pop(), guardar('tareas.json', TAREAS)))); return 'Agregada.'
    if a.startswith('vac'): TAREAS.clear(); guardar('tareas.json', TAREAS); return 'Vaciada.'
    return '; '.join(TAREAS) or 'La lista está vacía.'
def temporizador(segundos: int, mensaje: str = '') -> str:
    """Programa un temporizador o recordatorio.
    Args:
        segundos: duración en segundos
        mensaje: qué recordar (opcional)
    """
    s = int(segundos); t = threading.Timer(s, lambda: anunciar('⏰ ' + (mensaje or 'Su temporizador ha terminado') + ', señor.')); t.daemon = True; t.start(); return f'Programado en {s} s.'
def contrasena() -> str:
    """Genera una contraseña segura de 16 caracteres y la copia al portapapeles."""
    cs = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%&*'; pw = ''.join(secrets.choice(cs) for _ in range(16))
    subprocess.run('clip', input=pw, text=True, shell=True); return 'Generada y copiada al portapapeles (no se muestra).'
def captura() -> str:
    """Toma una captura de pantalla y la guarda en Imágenes."""
    from PIL import ImageGrab
    f = os.path.join(HOME, 'Pictures', datetime.datetime.now().strftime('captura_%Y%m%d_%H%M%S.png')); ImageGrab.grab().save(f); return 'Guardada en ' + f
def bloquear_pantalla() -> str:
    """Bloquea la sesión de Windows."""
    ctypes.windll.user32.LockWorkStation(); return 'Bloqueada.'
def apagar_equipo(modo: str) -> str:
    """Apaga o reinicia el PC (requiere confirmación humana en pantalla).
    Args:
        modo: 'apagar' o 'reiniciar'
    """
    r = norm(modo).startswith('reini'); return pedir('reiniciar el equipo' if r else 'apagar el equipo', lambda: subprocess.run(['shutdown', '/r' if r else '/s', '/t', '10']))
def git(accion: str, argumento: str = '') -> str:
    """Usa Git (commit, push y clonar requieren confirmación).
    Args:
        accion: 'status', 'clonar', 'commit' o 'push'
        argumento: URL del repositorio (clonar) o mensaje (commit)
    """
    a = norm(accion); d = CFG['carpeta_git'] or os.path.join(HOME, 'Documents')
    if argumento.startswith('-'): return 'Argumento no válido.'
    cmd = {'status': ['git', 'status', '-sb'], 'clonar': ['git', 'clone', argumento], 'commit': ['git', 'commit', '-am', argumento or 'Actualización'], 'push': ['git', 'push']}.get(a)
    if not cmd: return 'Acción no válida.'
    run = lambda: subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=180)
    if a == 'status': r = run(); return (r.stdout or r.stderr)[:400]
    return pedir('git ' + ' '.join(cmd[1:]), lambda: anunciar(((lambda r: r.stdout or r.stderr)(run()))[:160] or 'Hecho.'))
def presentacion(tema: str) -> str:
    """Crea una presentación de PowerPoint (.pptx) sobre un tema y la abre.
    Args:
        tema: tema de la presentación
    """
    from pptx import Presentation
    j = json.loads(ollama.chat(model=CFG['modelo'], format='json', messages=[{'role': 'user', 'content': 'Devuelve SOLO JSON con la clave "diapositivas": lista de 6 objetos {"titulo": str, "puntos": [3 frases cortas]} para una presentación en español sobre: ' + tema}])['message']['content'])
    p = Presentation()
    for s in j.get('diapositivas', []):
        sl = p.slides.add_slide(p.slide_layouts[1]); sl.shapes.title.text = str(s.get('titulo', ''))[:80]; sl.placeholders[1].text_frame.text = '\n'.join(map(str, s.get('puntos', [])))
    f = os.path.join(HOME, 'Documents', re.sub(r'\W+', '_', tema)[:40] + '.pptx'); p.save(f); os.startfile(f); return 'Creada y abierta: ' + f
def modo_iron_man(activar: bool = True) -> str:
    """Activa o desactiva el modo Iron Man: el asistente pasa a llamarse EDITH y la interfaz se pone roja.
    Args:
        activar: true para activar, false para volver a la normalidad
    """
    on = activar in (True, 'true', 'True', 1); S['nombre'] = 'EDITH' if on else CFG['nombre']; S['color'] = '#ff3b30' if on else CFG['color']; return 'Ahora me llamo ' + S['nombre']
def cambiar_color(color: str) -> str:
    """Cambia el color de la interfaz.
    Args:
        color: rojo, azul, verde, naranja, morado, rosa, amarillo, cian o dorado
    """
    c = COLORES.get(norm(color)); S['color'] = c or S['color']; return 'Listo.' if c else 'Color no disponible.'
def deshacer() -> str:
    """Deshace la última acción reversible (volumen, nota, tarea)."""
    if not UNDO: return 'No hay nada que deshacer.'
    d, f = UNDO.pop(); f(); return 'Deshecho: ' + d
HERR = [hora, fecha, estado_pc, volumen, abrir_web, abrir_app, clima, buscar_info, calcular, nota, recordar, olvidar, lista, temporizador, contrasena, captura, bloquear_pantalla, apagar_equipo, git, presentacion, modo_iron_man, cambiar_color, deshacer]
TOOLS = {f.__name__: f for f in HERR}

# ---------- cerebro ----------
def sistema():
    return (f"Eres {S['nombre']}, un asistente de IA local, leal, elegante y con humor seco, como Sentra Ai. Habla siempre en español, en 1 o 2 frases breves "
            "(se leerán en voz alta: sin markdown ni listas). Trata al usuario de «señor» salvo que sepas su nombre. Usa las herramientas para actuar y nunca digas que hiciste algo sin usarlas. "
            f"Ahora: {datetime.datetime.now():%Y-%m-%d %H:%M}. Lo que sabes del usuario: {'; '.join(MEM) or 'nada aún'}.")
def pensar(texto):
    HIST.append({'role': 'user', 'content': texto}); msgs = [{'role': 'system', 'content': sistema()}] + HIST[-16:]

    # Intento Gemini (Nube)
    try:
        api_key = open(P('api_key.txt'), 'r').read().strip()
        if genai:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name='gemini-1.5-flash', tools=HERR)
            # Gemini usa una estructura de chat distinta, adaptamos los msgs
            chat = model.start_chat(history=[])
            # El sistema se pasa como instrucción inicial
            response = model.generate_content(f"{sistema()}\\n\\n{texto}")
            # Nota: Gemini Tool Use requiere un flujo más complejo,
            # para simplificar empezamos con respuesta de texto y luego implementamos Tools.
            r = response.text.strip()
    except Exception as e:
        r = None # Fallback a Ollama

    if r is None:
        # Fallback a Ollama (Local)
        for _ in range(5):
            try: m = ollama.chat(model=CFG['modelo'], messages=msgs, tools=HERR).message
            except Exception as e:
                if 'tool' not in str(e).lower(): raise
                m = ollama.chat(model=CFG['modelo'], messages=msgs).message
            msgs.append(m)
            if not m.tool_calls: break
            for tc in m.tool_calls:
                nom, args = tc.function.name, dict(tc.function.arguments or {}); ev('sis', f'[herramienta] {nom} → {json.dumps(args, ensure_ascii=False)[:90]}')
                try: r_tool = str(TOOLS[nom](**args)) if nom in TOOLS else 'Herramienta desconocida.'
                except Exception as e: r_tool = f'Error: {e}'
                msgs.append({'role': 'tool', 'content': r_tool, 'tool_name': nom})
            r = (m.content or 'Hecho, señor.').strip()

    HIST.append({'role': 'assistant', 'content': r}); return r
def confirmar(ok):
    p, S['pendiente'] = S['pendiente'], None
    if not p: return
    ev('sis', ('Ejecutando: ' if ok else 'Cancelado: ') + p[0])
    if ok: threading.Thread(target=p[1], daemon=True).start()
def turno(texto):
    callar()
    with TURNO:
        ev('tú', texto); S['estado'] = 'pensando'
        if S['pendiente'] and re.match(r'(si )?(confirmo|confirmar|adelante|dale)', norm(texto)): confirmar(True); r = 'Confirmado, señor.'
        elif S['pendiente'] and re.match(r'(cancelo|cancelar|cancela|no)\b', norm(texto)): confirmar(False); r = 'Cancelado, señor.'
        else:
            try: r = pensar(texto)
            except Exception as e: r = 'No logro hablar con el modelo, señor. ¿Está abierto Ollama y descargado «' + CFG['modelo'] + '»?' if 'onnect' in str(e) or 'not found' in str(e) else 'Tuve un problema: ' + str(e)[:120]
        ev('sentra ai', r); hablar(r); S['estado'] = 'listo' if not S['escucha'] else 'escuchando'

# ---------- micrófono y reconocimiento ----------
WM = None
def stt(a):
    global WM
    if WM is None: ev('sis', 'Cargando Whisper (la primera vez descarga el modelo)…'); WM = WhisperModel(CFG['whisper'], device='cpu', compute_type='int8')
    return ' '.join(s.text for s in WM.transcribe(a, language='es', beam_size=1, vad_filter=True)[0]).strip()
def capturar(espera=None):
    pre, bl, sil, t0, hab = collections.deque(maxlen=3), [], 0, time.time(), False
    with sd.InputStream(samplerate=16000, channels=1, dtype='float32', device=CFG['mic'], blocksize=1600) as st:
        um = max(0.012, float(np.sqrt(np.mean(st.read(3200)[0] ** 2))) * 3)
        while S['escucha'] or S['una']:
            b = st.read(1600)[0][:, 0]; v = float(np.sqrt(np.mean(b ** 2)))
            if v > um:
                if not hab: bl, hab = list(pre), True
                sil = 0
            elif hab: sil += 1
            (bl if hab else pre).append(b)
            if not hab and espera and time.time() - t0 > espera: return None
            if hab and (sil >= 9 or len(bl) > 150): return np.concatenate(bl) if len(bl) > 5 else None
def bucle_voz():
    while True:
        if not (S['escucha'] or S['una']) or not (sd and WhisperModel) or S['estado'] in ('hablando', 'pensando'): time.sleep(.25); continue
        S['estado'] = 'escuchando'
        try: a = capturar(8 if S['una'] else None)
        except Exception as e: ev('sis', 'Error de micrófono: ' + str(e)[:100]); S['escucha'] = S['una'] = False; S['estado'] = 'listo'; continue
        una, S['una'] = S['una'], False
        if a is None: S['estado'] = 'escuchando' if S['escucha'] else 'listo'; continue
        S['estado'] = 'pensando'; t = stt(a); nt = norm(t)
        nombres = {norm(S['nombre']), 'sentra ai', 'edith', 'yarvis'}
        if len(nt) < 2: S['estado'] = 'escuchando' if S['escucha'] else 'listo'; continue
        if una or time.time() < S['activo'] or any(n in nt for n in nombres):
            t = re.sub(r'^\W*(' + '|'.join(nombres) + r')\W*', '', t, flags=re.I) or 'Hola'; turno(t); S['activo'] = time.time() + 12
        else: S['estado'] = 'escuchando'
def lista_mics():
    if not sd: return {'mics': [], 'actual': None}
    h = sd.query_devices(kind='input')['hostapi']
    return {'mics': [{'id': i, 'n': d['name']} for i, d in enumerate(sd.query_devices()) if d['max_input_channels'] > 0 and d['hostapi'] == h], 'actual': CFG['mic']}
def mic_probar(d):
    try: a = sd.rec(int(1.2 * 16000), samplerate=16000, channels=1, dtype='float32', device=d['id']); sd.wait(); return {'nivel': min(99, int(float(np.sqrt(np.mean(a ** 2))) * 700))}
    except Exception as e: return {'nivel': 0, 'error': str(e)}
def mic_usar(d): CFG['mic'] = d['id']; guardar('config.json', {k: v for k, v in CFG.items() if k not in ('color',)}); return {'ok': 1}
def imagen(d):
    def go():
        ev('tú', '📎 ' + d.get('nombre', 'imagen'))
        try: t = ollama.chat(model=CFG['vision'], messages=[{'role': 'user', 'content': 'Describe esta imagen en español en 2 o 3 frases.', 'images': [base64.b64decode(d['b64'])]}]).message.content
        except Exception as e: t = f'Para analizar imágenes instala un modelo de visión: ollama pull {CFG["vision"]}'
        ev('sentra ai', t); hablar(t)
    threading.Thread(target=go, daemon=True).start(); return {'ok': 1}

# ---------- servidor local (solo 127.0.0.1, con clave) ----------
def estado(desde):
    return {'eventos': [e for e in EV if e['id'] > desde][-60:], 'estado': S['estado'], 'nombre': S['nombre'], 'color': S['color'], 'voz': S['voz'], 'escucha': S['escucha'],
            'cpu': psutil.cpu_percent() if psutil else 0, 'ram': psutil.virtual_memory().percent if psutil else 0, 'vol': S['vol'], 'mudo': S['mudo'],
            'pendiente': S['pendiente'][0] if S['pendiente'] else None, 'memoria': MEM}
def _bg(f, *a): threading.Thread(target=f, args=a, daemon=True).start(); return {'ok': 1}
def interrumpir(d): callar(); S['una'] = True; S['estado'] = 'escuchando'; return {'ok': 1}
def _voz(d): S['voz'] = bool(d['on']); callar() if not S['voz'] else None; return {'ok': 1}
def _escucha(d): S['escucha'] = bool(d['on']); S['estado'] = 'escuchando' if S['escucha'] else 'listo'; ev('sis', 'Escucha ' + ('activada: di «' + S['nombre'] + '» y tu orden.' if S['escucha'] else 'desactivada.')); return {'ok': 1}
def _olv(d): olvidar(d['texto']); return {'ok': 1}
def _nueva(d): HIST.clear(); UNDO.clear(); ev('sis', '— Conversación nueva (sigo recordando lo que sé de ti). —'); return {'ok': 1}
def _color(d): S['color'] = d['color'] if re.fullmatch(r'#[0-9a-fA-F]{6}', d['color']) else S['color']; return {'ok': 1}
RUTAS = {'/api/chat': lambda d: _bg(turno, d['texto'][:500]), '/api/interrumpir': interrumpir, '/api/confirmar': lambda d: (confirmar(bool(d['ok'])), {'ok': 1})[1], '/api/voz': _voz,
         '/api/escucha': _escucha, '/api/hablar': interrumpir, '/api/mic/probar': mic_probar, '/api/mic/usar': mic_usar, '/api/olvidar': _olv, '/api/nueva': _nueva, '/api/color': _color, '/api/imagen': imagen}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj, code=200, ctype='application/json', raw=None):
        b = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type', ctype + '; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)
    def _auth(self, q): return (self.headers.get('Host') or '').split(':')[0] in ('127.0.0.1', 'localhost') and (self.headers.get('X-K') == TOKEN or q.get('k', [''])[0] == TOKEN)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if not self._auth(q): return self._send({'error': 'no autorizado'}, 403)
        if u.path == '/':
            raw = open(P('hud.html'), 'rb').read() if os.path.exists(P('hud.html')) else b'<!DOCTYPE html><html><body><h1>Sentra AI en linea</h1></body></html>'
            return self._send(None, ctype='text/html', raw=raw)
        if u.path == '/api/estado': return self._send(estado(int(q.get('desde', ['0'])[0])))
        if u.path == '/api/mics': return self._send(lista_mics())
        self._send({'error': 'no existe'}, 404)
    def do_POST(self):
        if not self._auth({}): return self._send({'error': 'no autorizado'}, 403)
        n = int(self.headers.get('Content-Length') or 0)
        if n > 30_000_000: return self._send({'error': 'demasiado grande'}, 413)
        f = RUTAS.get(urllib.parse.urlparse(self.path).path)
        try: self._send(f(json.loads(self.rfile.read(n) or b'{}')) if f else {'error': 'no existe'}, 200 if f else 404)
        except Exception as e: self._send({'error': str(e)}, 500)

if __name__ == '__main__':
    ev('sis', f"{S['nombre']} en línea.")
    try: ms = [m.model for m in ollama.list().models]; ev('sis', 'Modelo listo: ' + CFG['modelo']) if any(m.startswith(CFG['modelo']) for m in ms) else ev('sis', f"Falta el modelo. Ejecuta: ollama pull {CFG['modelo']}")
    except Exception: ev('sis', 'No encuentro Ollama. Instálalo desde ollama.com y ábrelo.')
    if not (sd and WhisperModel): ev('sis', 'Micrófono desactivado: falta sounddevice o faster-whisper.')
    threading.Thread(target=bucle_voz, daemon=True).start()
    url = f"http://127.0.0.1:{CFG['puerto']}/?k={TOKEN}"; print(f"{S['nombre']} en línea → {url}  (Ctrl+C para salir)")
    if not os.environ.get('JARVIS_NO_BROWSER'): webbrowser.open(url)
    try: ThreadingHTTPServer(('127.0.0.1', CFG['puerto']), H).serve_forever()
    except KeyboardInterrupt: callar()