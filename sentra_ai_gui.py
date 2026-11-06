#!/usr/bin/env python3
"""Sentra Ai · asistente local con interfaz HUD propia (tkinter). Uso:  python sentra_ai_gui.py"""
import os, sys, json, time, ast, re, base64, secrets, threading, subprocess, webbrowser, datetime, operator, ctypes, unicodedata, collections
import urllib.request, urllib.parse

def _imp(n):
    try: return __import__(n)
    except Exception: return None
ollama, psutil, sd, np = _imp('ollama'), _imp('psutil'), _imp('sounddevice'), _imp('numpy')
try: from faster_whisper import WhisperModel
except Exception: WhisperModel = None

AQUI = os.path.dirname(os.path.abspath(__file__)); P = lambda f: os.path.join(AQUI, f)
HOME = os.path.expanduser('~')
CFG = {'nombre': 'Sentra Ai', 'modelo': 'llama3.1', 'vision': 'llava', 'whisper': 'small', 'mic': None, 'voz': '', 'puerto': 8765, 'color': '#00e5ff', 'carpeta_git': ''}
def cargar(f, d):
    try: return json.load(open(P(f), encoding='utf-8'))
    except Exception: return d
def guardar(f, v): json.dump(v, open(P(f), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
CFG.update(cargar('config.json', {})); MEM = cargar('memoria.json', []); TAREAS = cargar('tareas.json', [])
S = {'estado': 'listo', 'nombre': CFG['nombre'], 'color': CFG['color'], 'voz': True, 'escucha': False, 'una': False, 'activo': 0, 'pendiente': None, 'vol': 50, 'mudo': False}
EV, UNDO, HIST, TURNO = [], [], [], threading.Lock()
def ev(q, t): EV.append({'id': len(EV) + 1, 'q': q, 't': t})
def norm(s): return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn').strip()

# ---------- voz de salida (PowerShell/System.Speech: se puede interrumpir al instante) ----------
PS = ("Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
      "$c=New-Object Globalization.CultureInfo 'es-ES';if($env:JVOZ){try{$s.SelectVoice($env:JVOZ)}catch{}}"
      "else{try{$s.SelectVoiceByHints('Male','NotSet',0,$c)}catch{try{$s.SelectVoiceByHints('NotSet','NotSet',0,$c)}catch{}}};$s.Speak($env:JTXT)")
_tts = None
def callar():
    if _tts and _tts.poll() is None: _tts.kill()
def hablar(t):
    global _tts
    callar()
    if not S['voz'] or sys.platform != 'win32': return
    S['estado'] = 'hablando'
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
    for _ in range(5):
        try: m = ollama.chat(model=CFG['modelo'], messages=msgs, tools=HERR).message
        except Exception as e:
            if 'tool' not in str(e).lower(): raise
            m = ollama.chat(model=CFG['modelo'], messages=msgs).message
        msgs.append(m)
        if not m.tool_calls: break
        for tc in m.tool_calls:
            nom, args = tc.function.name, dict(tc.function.arguments or {}); ev('sis', f'[herramienta] {nom} → {json.dumps(args, ensure_ascii=False)[:90]}')
            try: r = str(TOOLS[nom](**args)) if nom in TOOLS else 'Herramienta desconocida.'
            except Exception as e: r = f'Error: {e}'
            msgs.append({'role': 'tool', 'content': r, 'tool_name': nom})
    r = (m.content or 'Hecho, señor.').strip(); HIST.append({'role': 'assistant', 'content': r}); return r
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

# ---------- interfaz HUD (tkinter: viene con Python, no hay que instalar nada) ----------
import tkinter as tk, queue, math, random
from tkinter import colorchooser, filedialog
BG, PANEL, TX, MUT, AMB = '#070b10', '#0b1219', '#cfe8ef', '#6b7c86', '#ffb300'
UIQ = queue.Queue()
def mix(c, a, bg=BG):
    c, b = c.lstrip('#'), bg.lstrip('#'); return '#%02x%02x%02x' % tuple(int(int(c[i:i + 2], 16) * a + int(b[i:i + 2], 16) * (1 - a)) for i in (0, 2, 4))
def interrumpir():
    callar()
    if sd and WhisperModel: S['una'] = True; S['estado'] = 'escuchando'
    else: ev('sis', 'Interrumpido. (Para hablarme falta sounddevice o faster-whisper.)')
def lanzar(t): threading.Thread(target=turno, args=(t,), daemon=True).start()
CHIPS = ['¿Qué hora es?', 'Estado de mi PC', 'Abre YouTube', 'Sube el volumen', 'Deshaz eso', '¿Cómo está el clima en Bogotá?', 'Crea una presentación sobre energía solar', 'Busca información sobre los agujeros negros',
         'Calcula 25*4+10', 'Pon un temporizador de 10 segundos', 'Agrega leche a mi lista', '¿Qué hay en mi lista?', 'Abre la calculadora', 'Toma una captura de pantalla', 'Genera una contraseña segura',
         'Modo Iron Man', 'Cambia el color a azul', 'Me llamo Ana y me gusta la música', '¿Qué sabes de mí?', 'Apaga el equipo', 'Cuéntame un chiste']
AYUDA = """Escribe o di órdenes naturales. Ejemplos:

Sistema:      «¿qué hora es?», «estado de mi PC», «sube/baja el volumen», «silencia», «captura de pantalla», «bloquea el equipo», «apaga el equipo» (pide confirmación)
Apps y web:   «abre YouTube», «busca gatos en YouTube», «abre la calculadora», «abre Spotify»
Información:  «clima en Bogotá», «busca información sobre los agujeros negros», «calcula 15% de 200 (0.15*200)»
Trabajo:      «crea una presentación sobre energía solar», «haz commit con el mensaje X», «haz push», «clona <url>», «git status»
Organización: «agrega leche a mi lista», «¿qué hay en mi lista?», «pon un temporizador de 5 minutos», «recuérdame estirarme en 20 minutos», «guarda una nota que diga...»
Memoria:      «me llamo Ana», «recuerda que me gusta el fútbol», «¿qué sabes de mí?», «olvida todo», «deshaz eso»
Modos:        «modo Iron Man» (pasa a EDITH), «cambia el color a rojo», botón IMAGEN para analizar una foto
Voz:          botón HABLAR o Ctrl+Espacio (te escucha una frase) · ESCUCHA: ON (di el nombre y tu orden) · tocar el núcleo me interrumpe"""

class HUD:
    def __init__(s):
        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception: pass
        r = s.r = tk.Tk(); r.geometry('1120x740'); r.minsize(860, 600); r.configure(bg=BG); r.protocol('WM_DELETE_WINDOW', s.cerrar)
        s.fase, s.nivel, s.ult, s.col, s.nom, s.acc, s.mem_w = 0.0, .06, 0, '', '', [], None
        h = tk.Frame(r, bg=BG); h.pack(fill='x', padx=16, pady=(10, 2))
        s.tit = tk.Label(h, bg=BG, font=('Segoe UI', 20, 'bold')); s.tit.config(text='SENTRA AI'); s.tit.pack(side='left'); s.acc.append((s.tit, 'fg'))
        tk.Label(h, text='SENTRA v1', bg=BG, fg=AMB, font=('Segoe UI', 8), padx=6, highlightbackground=AMB, highlightthickness=1).pack(side='left', padx=12)
        s.lvol = tk.Label(h, text='VOL 50', bg=BG, font=('Segoe UI', 9)); s.lvol.pack(side='right'); s.acc.append((s.lvol, 'fg'))
        s.bram, s.bcpu = s.barra(h, 'RAM'), s.barra(h, 'CPU')
        m = tk.Frame(r, bg=BG); m.pack(fill='both', expand=True, padx=16, pady=6); m.columnconfigure(0, weight=5); m.columnconfigure(1, weight=4); m.rowconfigure(0, weight=1)
        iz = tk.Frame(m, bg=BG); iz.grid(row=0, column=0, sticky='nsew')
        s.cv = tk.Canvas(iz, bg=BG, highlightthickness=0, cursor='hand2'); s.cv.pack(fill='both', expand=True); s.cv.bind('<Button-1>', lambda e: interrumpir())
        s.lest = tk.Label(iz, text='EN LÍNEA', bg=BG, font=('Segoe UI', 13)); s.lest.pack(pady=(0, 6)); s.acc.append((s.lest, 'fg'))
        dr = tk.Frame(m, bg=BG); dr.grid(row=0, column=1, sticky='nsew', padx=(14, 0))
        s.log = tk.Text(dr, bg=PANEL, fg=TX, wrap='word', relief='flat', state='disabled', font=('Segoe UI', 10), padx=10, pady=8, highlightthickness=1, highlightbackground='#16313b')
        sb = tk.Scrollbar(dr, command=s.log.yview); s.log.config(yscrollcommand=sb.set); sb.pack(side='right', fill='y'); s.log.pack(side='top', fill='both', expand=True)
        s.log.tag_config('tu', foreground='#9aa7b0'); s.log.tag_config('sis', foreground=MUT); s.log.tag_config('n', font=('Segoe UI', 10, 'bold'))
        s.av = tk.Frame(dr, bg='#2a1a05', highlightbackground=AMB, highlightthickness=1)
        s.avt = tk.Label(s.av, bg='#2a1a05', fg='#ffcf66', wraplength=330, justify='left', font=('Segoe UI', 10)); s.avt.pack(side='left', padx=8, pady=8)
        for t, ok in (('CANCELAR', False), ('CONFIRMAR', True)): tk.Button(s.av, text=t, command=lambda ok=ok: confirmar(ok), bg='#2a1a05', fg='#ffcf66', relief='flat', padx=8).pack(side='right', padx=4)
        s.ch = tk.Text(r, height=3, bg=BG, relief='flat', cursor='arrow', highlightthickness=0, wrap='word'); s.ch.pack(fill='x', padx=14)
        for t in CHIPS:
            b = tk.Button(s.ch, text=t, command=lambda t=t: lanzar(t), bg=PANEL, fg=TX, activebackground='#12303d', activeforeground=TX, relief='flat', font=('Segoe UI', 8), padx=8, cursor='hand2'); s.ch.window_create('end', window=b, padx=2, pady=2)
        s.ch.config(state='disabled')
        f = tk.Frame(r, bg=BG); f.pack(fill='x', padx=16, pady=(6, 4))
        s.en = tk.Entry(f, bg=PANEL, fg=TX, insertbackground=TX, relief='flat', font=('Segoe UI', 11), highlightthickness=1, highlightbackground='#16313b', highlightcolor='#33d6ff'); s.en.pack(fill='x', ipady=7)
        s.en.bind('<Return>', s.enviar); r.bind('<Control-space>', lambda e: interrumpir()); s.en.focus_set()
        bs = tk.Frame(r, bg=BG); bs.pack(fill='x', padx=13, pady=(0, 12))
        s.btn(bs, '🎤 HABLAR', interrumpir); s.bes = s.btn(bs, 'ESCUCHA: OFF', s.t_escucha); s.bvoz = s.btn(bs, 'VOZ: SÍ', s.t_voz); s.btn(bs, 'MICRÓFONO', s.abrir_mic); s.btn(bs, 'MEMORIA', s.abrir_mem)
        s.btn(bs, 'COMANDOS', s.abrir_ayuda); s.btn(bs, 'IMAGEN', s.imagen); s.btn(bs, 'COLOR', s.color); s.btn(bs, 'NUEVA', s.nueva)
        s.recolor(); s.dibujar(); s.poll(); s.metricas()
        if os.environ.get('JARVIS_TEST'): r.after(2500, r.destroy)
    def barra(s, p, nom):
        cv = tk.Canvas(p, width=110, height=8, bg=PANEL, highlightthickness=0); it = cv.create_rectangle(0, 0, 0, 8, outline='', fill=S['color']); cv.pack(side='right', padx=(4, 12))
        tk.Label(p, text=nom, bg=BG, fg=TX, font=('Segoe UI', 8)).pack(side='right'); s.acc.append((cv, it)); return cv, it
    def btn(s, p, txt, cmd):
        b = tk.Button(p, text=txt, command=cmd, bg=PANEL, fg=S['color'], activebackground='#12303d', activeforeground=TX, relief='flat', font=('Segoe UI', 9), padx=10, pady=6, cursor='hand2', highlightthickness=1, highlightbackground='#14424f')
        b.pack(side='left', padx=3); s.acc.append((b, 'fg')); return b
    def recolor(s):
        s.col = S['color']
        for w, o in s.acc:
            try: w.itemconfig(o, fill=s.col) if isinstance(o, int) else w.config(**{o: s.col})
            except Exception: pass
        s.log.tag_config('sentra ai', foreground=s.col)
    def add(s, e):
        q = {'tú': ('Tú', 'tu'), 'sis': ('Sistema', 'sis'), 'sentra ai': (S['nombre'], 'sentra ai')}[e['q']]
        s.log.config(state='normal'); s.log.insert('end', q[0] + ' · ', ('n', q[1])); s.log.insert('end', e['t'] + '\n\n', q[1]); s.log.config(state='disabled'); s.log.see('end')
    def enviar(s, _=None):
        t = s.en.get().strip(); s.en.delete(0, 'end')
        if t: lanzar(t)
    def poll(s):
        while not UIQ.empty(): UIQ.get()()
        for e in EV[s.ult:]: s.add(e)
        s.ult = len(EV)
        if S['color'] != s.col: s.recolor()
        # Forzamos el nombre aquí para que no dependa de nada más
        s.nom = "Sentra Ai"
        s.tit.config(text=s.nom.upper())
        s.r.title(s.nom)
        s.lest.config(text={'listo': 'EN LÍNEA', 'escuchando': 'ESCUCHANDO', 'pensando': 'PENSANDO', 'hablando': 'HABLANDO'}.get(S['estado'], ''))
        s.bes.config(text='ESCUCHA: ' + ('ON' if S['escucha'] else 'OFF')); s.bvoz.config(text='VOZ: ' + ('SÍ' if S['voz'] else 'NO')); s.lvol.config(text='VOL ✕' if S['mudo'] else f"VOL {S['vol']}")
        if S['pendiente']:
            s.avt.config(text=f"{s.nom} quiere: {S['pendiente'][0]}. ¿Lo confirmas? (también puedes decir «confirmo»)")
            if not s.av.winfo_ismapped(): s.av.pack(fill='x', pady=(8, 0))
        elif s.av.winfo_ismapped(): s.av.pack_forget()
        if s.mem_w and s.mem_w.winfo_exists(): s.pint_mem()
        s.r.after(100, s.poll)
    def metricas(s):
        if psutil:
            for (cv, it), v in ((s.bcpu, psutil.cpu_percent()), (s.bram, psutil.virtual_memory().percent)): cv.coords(it, 0, 0, 110 * v / 100, 8)
        s.r.after(1000, s.metricas)
    def dibujar(s):
        c = s.cv; W, H = c.winfo_width(), c.winfo_height(); c.delete('all')
        if W > 10 and H > 10:
            est = S['estado']; s.fase += .033 * (3 if est == 'pensando' else 1)
            obj = {'listo': .06, 'escuchando': .28 + .15 * math.sin(s.fase * 4), 'pensando': .18, 'hablando': .35 + .45 * random.random()}.get(est, .06); s.nivel += (obj - s.nivel) * .25
            n, f, col, cx, cy, r = s.nivel, s.fase, S['color'], W / 2, H / 2, min(W, H) * .26
            for k in range(8, 0, -1): rr = r * (1 + .85 * k / 8); c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=mix(col, (.05 + .3 * n) * (1 - k / 9)), outline='')
            for i in range(72):
                a = 2 * math.pi * i / 72 + f * .15; amp = n * (.5 + .5 * math.sin(f * 3 + i * .6)) * (.5 + .5 * math.sin(i * .37 - f * 2)); r1, r2 = r * 1.22, r * (1.26 + .55 * amp)
                c.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a), cx + r2 * math.cos(a), cy + r2 * math.sin(a), fill=mix(col, .43 + .55 * amp), width=2, capstyle='round')
            for i in range(3):
                rr = r * 1.05 if i == 0 else r * (.84 - .1 * (i - 1)); ini = f * (40 + 25 * i) * (-1 if i % 2 else 1) * 57.3 / 10
                for k in range(3): c.create_arc(cx - rr, cy - rr, cx + rr, cy + rr, start=ini + 120 * k, extent=70, style='arc', outline=mix(col, (190 - 45 * i) / 255), width=max(1, 3 - i))
            rn = r * (.52 + .08 * n)
            for k in range(10, 0, -1): q = rn * k / 10; c.create_oval(cx - q, cy - q, cx + q, cy + q, fill=mix('#ffffff', .9 * (1 - k / 10), mix(col, .55)), outline='')
        s.r.after(33, s.dibujar)
    def t_escucha(s):
        if S['escucha']: S['escucha'] = False; S['estado'] = 'listo'; ev('sis', 'Escucha desactivada.')
        elif sd and WhisperModel: S['escucha'] = True; S['estado'] = 'escuchando'; ev('sis', f"Escucha activada: di «{S['nombre']}» y tu orden.")
        else: ev('sis', 'Falta sounddevice o faster-whisper para escuchar.')
    def t_voz(s):
        S['voz'] = not S['voz']
        if not S['voz']: callar()
    def nueva(s): HIST.clear(); UNDO.clear(); ev('sis', '— Conversación nueva (sigo recordando lo que sé de ti). —')
    def color(s):
        c = colorchooser.askcolor(color=S['color'], parent=s.r)[1]
        if c: S['color'] = c
    def imagen(s):
        f = filedialog.askopenfilename(parent=s.r, filetypes=[('Imágenes', '*.png *.jpg *.jpeg *.webp *.gif')])
        if f: imagen({'nombre': os.path.basename(f), 'b64': base64.b64encode(open(f, 'rb').read()).decode()})
    def modal(s, tit, w, h):
        t = tk.Toplevel(s.r); t.title(tit); t.geometry(f'{w}x{h}'); t.configure(bg=BG); t.transient(s.r)
        tk.Label(t, text=tit, bg=BG, fg=S['color'], font=('Segoe UI', 13, 'bold')).pack(anchor='w', padx=14, pady=(12, 4)); return t
    def lista(s, w):
        lb = tk.Listbox(w, bg=PANEL, fg=TX, selectbackground='#12414f', relief='flat', font=('Segoe UI', 10), highlightthickness=0, activestyle='none'); lb.pack(fill='both', expand=True, padx=14, pady=4); return lb
    def fila(s, w, *bt):
        f = tk.Frame(w, bg=BG); f.pack(fill='x', padx=11, pady=10)
        for t, c in bt: tk.Button(f, text=t, command=c, bg=PANEL, fg=S['color'], relief='flat', padx=10, pady=5, font=('Segoe UI', 9)).pack(side='left', padx=3)
    def abrir_ayuda(s):
        w = s.modal('COMANDOS', 820, 460); t = tk.Text(w, bg=PANEL, fg=TX, relief='flat', wrap='word', font=('Consolas', 10), padx=12, pady=10); t.insert('1.0', AYUDA); t.config(state='disabled'); t.pack(fill='both', expand=True, padx=14, pady=6); s.fila(w, ('Cerrar', w.destroy))
    def abrir_mem(s):
        s.mem_w = s.modal('MEMORIA DE ' + S['nombre'], 520, 380); s.mem_lb = s.lista(s.mem_w); s.mem_ult = None
        s.fila(s.mem_w, ('Olvidar seleccionado', s.olv), ('Cerrar', s.mem_w.destroy)); s.pint_mem()
    def pint_mem(s):
        if s.mem_ult != list(MEM): s.mem_ult = list(MEM); s.mem_lb.delete(0, 'end'); [s.mem_lb.insert('end', m) for m in MEM]
    def olv(s):
        i = s.mem_lb.curselection()
        if i: olvidar(MEM[i[0]])
    def abrir_mic(s):
        s.mw = s.modal('MICRÓFONO', 620, 420); d = lista_mics(); s.mics, s.niv = d['mics'], {}
        tk.Label(s.mw, text='Mide tus micrófonos reales y te dice cuál recibe voz (el «predeterminado» de Windows a veces es uno muerto).', bg=BG, fg=MUT, wraplength=580, justify='left').pack(anchor='w', padx=14)
        s.mlb = s.lista(s.mw); s.mest = tk.Label(s.mw, bg=BG, fg=TX, wraplength=580, justify='left', text='Pulsa BUSCAR EL QUE FUNCIONA y habla mientras mide.' if s.mics else 'No encontré micrófonos (¿falta sounddevice?).'); s.mest.pack(anchor='w', padx=14)
        s.fila(s.mw, ('Probar seleccionado', lambda: s.medir(s.sel_mic())), ('Buscar el que funciona', lambda: s.medir([m['id'] for m in s.mics])), ('Usar este', s.usar_mic), ('Cerrar', s.mw.destroy)); s.pint_mic()
    def sel_mic(s): i = s.mlb.curselection(); return [s.mics[i[0]]['id']] if i else []
    def pint_mic(s, sel=None):
        s.mlb.delete(0, 'end')
        for m in s.mics:
            v = s.niv.get(m['id']); s.mlb.insert('end', ('·' if v is None else f'✓ {v}%' if v >= 8 else '✗ sin señal') + '   ' + m['n'] + ('   (en uso)' if m['id'] == CFG['mic'] else ''))
        if sel is not None: s.mlb.selection_set(sel)
    def medir(s, ids):
        if not ids: return
        S['escucha'] = False
        def go():
            mejor, mn = None, -1
            for i in ids:
                nom = next(m['n'] for m in s.mics if m['id'] == i); UIQ.put(lambda nom=nom: s.mest.config(text='HABLA AHORA (cuenta o lee algo en voz alta)…  probando: ' + nom))
                v = mic_probar({'id': i})['nivel']; s.niv[i] = v; UIQ.put(s.pint_mic)
                if v > mn: mn, mejor = v, i
            pos = next((k for k, m in enumerate(s.mics) if m['id'] == mejor), None)
            msg = f'El que mejor capta tu voz: {s.mics[pos]["n"]} ({mn}%). Pulsa USAR ESTE.' if len(ids) > 1 and mn >= 8 else 'Ninguno captó voz. Revisa que no esté silenciado.' if mn < 8 else 'Prueba terminada. Elige uno y pulsa USAR ESTE.'
            UIQ.put(lambda: (s.pint_mic(pos if mn >= 8 else None), s.mest.config(text=msg)))
        threading.Thread(target=go, daemon=True).start()
    def usar_mic(s):
        i = s.sel_mic()
        if i: mic_usar({'id': i[0]}); s.pint_mic(); s.mest.config(text='Listo: usaré ese micrófono.'); ev('sis', 'Micrófono elegido.')
    def cerrar(s): callar(); s.r.destroy()
    def run(s): s.r.mainloop()

if __name__ == '__main__':
    ev('sis', f"{S['nombre']} en línea.")
    try: ms = [m.model for m in ollama.list().models]; ev('sis', 'Modelo listo: ' + CFG['modelo']) if any(m.startswith(CFG['modelo']) for m in ms) else ev('sis', f"Falta el modelo. Ejecuta: ollama pull {CFG['modelo']}")
    except Exception: ev('sis', 'No encuentro Ollama. Instálalo desde ollama.com y ábrelo.')
    if not (sd and WhisperModel): ev('sis', 'Micrófono desactivado: falta sounddevice o faster-whisper.')
    threading.Thread(target=bucle_voz, daemon=True).start(); HUD().run()
