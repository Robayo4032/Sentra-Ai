#!/usr/bin/env python3
"""
Sentra Ai · asistente local con interfaz HUD propia (tkinter) y acceso móvil.
Creado por Derek · github.com/DerekAI
Uso:  python sentra_ai_gui.py
"""
import os, sys, json, time, ast, re, base64, secrets, threading, subprocess, webbrowser, datetime, operator, ctypes, unicodedata, collections, socket, io
import urllib.request, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

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
def turno(texto, origen='tú'):
    callar()
    with TURNO:
        ev(origen, texto); S['estado'] = 'pensando'
        if S['pendiente'] and re.match(r'(si )?(confirmo|confirmar|adelante|dale)', norm(texto)): confirmar(True); r = 'Confirmado, señor.'
        elif S['pendiente'] and re.match(r'(cancelo|cancelar|cancela|no)\b', norm(texto)): confirmar(False); r = 'Cancelado, señor.'
        else:
            try: r = pensar(texto)
            except Exception as e: r = 'No logro hablar con el modelo, señor. ¿Está abierto Ollama y descargado «' + CFG['modelo'] + '»?' if 'onnect' in str(e) or 'not found' in str(e) else 'Tuve un problema: ' + str(e)[:120]
        ev('sentra ai', r); hablar(r); S['estado'] = 'listo' if not S['escucha'] else 'escuchando'
        return r

# ---------- servidor móvil local ----------
def obtener_ips():
    ips = []
    # 1. Detectar la IP que conecta con el router de internet (la interfaz de red real)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip_salida = s.getsockname()[0]
        s.close()
        if ip_salida and not ip_salida.startswith('127.'):
            ips.append(ip_salida)
    except Exception:
        pass
    # 2. Agregar otras interfaces de red reales (excluyendo adaptadores virtuales como VirtualBox 192.168.56.x o APIPA 169.254.x.x)
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and not ip.startswith('127.'):
                if ip.startswith('192.168.56.') or ip.startswith('169.254.'):
                    continue
                ips.append(ip)
    except Exception:
        pass
    return ips or ['127.0.0.1']

def obtener_ip_local():
    return obtener_ips()[0]

class SentraMobileHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/ask':
            q = urllib.parse.parse_qs(u.query).get('q', [''])[0].strip()
            res = turno(q, origen='tú (móvil)') if q else "No recibí ninguna pregunta, señor."
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write((res or 'Listo, señor.').encode('utf-8'))
        elif u.path == '/api/estado':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'estado': S['estado'], 'nombre': S['nombre']}, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>{S['nombre']} Móvil</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
body{{background:#070b10;color:#cfe8ef;display:flex;flex-direction:column;height:100vh;height:100dvh}}
header{{background:#0b1219;border-bottom:1px solid #14424f;padding:12px 16px;display:flex;justify-content:space-between;align-items:center}}
.title{{color:#00e5ff;font-weight:bold;letter-spacing:1px;font-size:1.1rem}}
.status{{font-size:0.75rem;color:#22e07a;font-weight:bold;text-transform:uppercase;border:1px solid #22e07a;padding:2px 8px;border-radius:10px}}
#chat{{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;-webkit-overflow-scrolling:touch}}
.msg{{padding:10px 14px;border-radius:14px;max-width:85%;font-size:0.95rem;line-height:1.4;word-break:break-word}}
.msg.user{{align-self:flex-end;background:#1b2a35;color:#fff;border-bottom-right-radius:2px}}
.msg.ai{{align-self:flex-start;background:#0b1219;border:1px solid #14424f;color:#cfe8ef;border-bottom-left-radius:2px}}
.msg.ai.thinking{{color:#00e5ff;font-style:italic}}
#input-form{{display:flex;gap:8px;padding:12px;background:#0b1219;border-top:1px solid #14424f}}
#txt{{flex:1;background:#070b10;border:1px solid #16313b;border-radius:20px;padding:10px 16px;color:#fff;font-size:1rem;outline:none}}
#txt:focus{{border-color:#00e5ff}}
button{{background:#00e5ff;color:#070b10;border:none;border-radius:20px;padding:10px 18px;font-weight:bold;font-size:0.95rem;cursor:pointer}}
</style></head>
<body>
<header><div class="title">{S['nombre']}</div><div class="status" id="st">CONECTADO</div></header>
<div id="chat"><div class="msg ai">Hola, señor. Todo listo en su móvil. ¿Qué desea que haga?</div></div>
<form id="input-form" onsubmit="event.preventDefault(); send();">
  <input type="text" id="txt" placeholder="Escribe a {S['nombre']}..." autocomplete="off">
  <button type="submit">Enviar</button>
</form>
<script>
async function send(){{
  const inp=document.getElementById('txt'); const txt=inp.value.trim(); if(!txt)return; inp.value='';
  const chat=document.getElementById('chat'); const uDiv=document.createElement('div'); uDiv.className='msg user'; uDiv.innerText=txt; chat.appendChild(uDiv);
  const aDiv=document.createElement('div'); aDiv.className='msg ai thinking'; aDiv.innerText='Pensando...'; chat.appendChild(aDiv); chat.scrollTop=chat.scrollHeight;
  try{{
    const res=await fetch('/ask?q='+encodeURIComponent(txt)); const ans=await res.text();
    aDiv.className='msg ai'; aDiv.innerText=ans;
  }}catch(e){{ aDiv.className='msg ai'; aDiv.innerText='Error al comunicarse con Sentra. Revisa que tu celular y PC sigan en el mismo Wi-Fi.'; }}
  chat.scrollTop=chat.scrollHeight;
}}
</script></body></html>'''
            self.wfile.write(html.encode('utf-8'))

def iniciar_servidor_movil():
    try:
        ip = obtener_ip_local()
        srv = ThreadingHTTPServer(('0.0.0.0', CFG['puerto']), SentraMobileHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return ip
    except Exception:
        return '127.0.0.1'

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
        r = s.r = tk.Tk(); r.geometry('1160x780'); r.minsize(900, 640); r.configure(bg=BG); r.protocol('WM_DELETE_WINDOW', s.cerrar)
        s.fase, s.nivel, s.ult, s.col, s.nom, s.acc, s.mem_w = 0.0, .06, 0, '', '', [], None

        # ---------- BARRA SUPERIOR (HEADER HUD) ----------
        h = tk.Frame(r, bg='#060a0f', highlightthickness=1, highlightbackground='#101c27')
        h.pack(fill='x', padx=12, pady=(8, 2), ipady=3)
        
        # Logo y badges
        s.tit = tk.Label(h, bg='#060a0f', font=('Segoe UI', 16, 'bold'), text='SENTRA AI')
        s.tit.pack(side='left', padx=(10, 6))
        s.acc.append((s.tit, 'fg'))
        
        s.badge_ver = tk.Label(h, text='STARK EXPO', bg='#060a0f', fg=S['color'], font=('Consolas', 7, 'bold'), padx=5, pady=1, highlightbackground=S['color'], highlightthickness=1)
        s.badge_ver.pack(side='left', padx=4)
        s.acc.append((s.badge_ver, 'fg')); s.acc.append((s.badge_ver, 'highlightbackground'))

        s.badge_mod = tk.Label(h, text='MODE: ' + CFG['modelo'].upper(), bg='#0b1924', fg='#38bdf8', font=('Consolas', 7, 'bold'), padx=5, pady=2)
        s.badge_mod.pack(side='left', padx=4)

        # Reloj central en vivo
        s.clock_lbl = tk.Label(h, text='--:--:--', bg='#060a0f', fg=S['color'], font=('Consolas', 11, 'bold'))
        s.clock_lbl.pack(side='right', padx=(10, 16))
        s.acc.append((s.clock_lbl, 'fg'))

        # Métricas lado derecho
        s.lvol = tk.Label(h, text='VOL 50%', bg='#060a0f', fg=TX, font=('Consolas', 8, 'bold'))
        s.lvol.pack(side='right', padx=(4, 10))
        s.bram = s.barra(h, 'RAM')
        s.bcpu = s.barra(h, 'CPU')

        # ---------- CUERPO PRINCIPAL (2 COLUMNAS) ----------
        m = tk.Frame(r, bg='#04070b'); m.pack(fill='both', expand=True, padx=12, pady=4)
        m.columnconfigure(0, weight=6); m.columnconfigure(1, weight=5); m.rowconfigure(0, weight=1)

        # Panel izquierdo: Canvas con Pistas de Cobre y Núcleo Holográfico
        iz = tk.Frame(m, bg='#04070b', highlightthickness=1, highlightbackground='#0e1b26')
        iz.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        s.cv = tk.Canvas(iz, bg='#04070b', highlightthickness=0, cursor='hand2')
        s.cv.pack(fill='both', expand=True)
        s.cv.bind('<Button-1>', lambda e: interrumpir())

        # Panel derecho: Consola de Comunicaciones + Botones de Control
        dr = tk.Frame(m, bg='#060a0f', highlightthickness=1, highlightbackground='#101f2c')
        dr.grid(row=0, column=1, sticky='nsew', padx=(6, 0))

        # Encabezado con telemetría
        header_chat = tk.Frame(dr, bg='#091119', highlightthickness=1, highlightbackground='#132433')
        header_chat.pack(fill='x', ipady=3)
        tk.Label(header_chat, text='COMMUNICATIONS FEED // PROTOCOLO ACTIVO', bg='#091119', fg='#527588', font=('Consolas', 8, 'bold')).pack(side='left', padx=10)
        
        top_meter = tk.Canvas(header_chat, height=4, width=80, bg='#091119', highlightthickness=0)
        top_meter.create_rectangle(0, 0, 50, 4, fill='#00e5ff', outline='')
        top_meter.pack(side='right', padx=10)

        # Feed de log
        s.log = tk.Text(dr, bg='#03060a', fg=TX, wrap='word', relief='flat', state='disabled', font=('Segoe UI', 10), padx=12, pady=8, highlightthickness=0)
        sb = tk.Scrollbar(dr, command=s.log.yview)
        s.log.config(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        s.log.pack(side='top', fill='both', expand=True)

        s.log.tag_config('tu', foreground='#38bdf8', font=('Segoe UI', 10, 'bold'))
        s.log.tag_config('movil', foreground='#c084fc', font=('Segoe UI', 10, 'bold'))
        s.log.tag_config('sentra ai', foreground='#00e5ff', font=('Segoe UI', 10, 'bold'))
        s.log.tag_config('sis', foreground='#94a3b8', font=('Segoe UI', 9, 'italic'))
        s.log.tag_config('time', foreground='#475569', font=('Consolas', 8))
        s.log.tag_config('n', font=('Segoe UI', 10, 'bold'))

        # Banner de confirmación para acciones críticas
        s.av = tk.Frame(dr, bg='#2a1a05', highlightbackground=AMB, highlightthickness=1)
        s.avt = tk.Label(s.av, bg='#2a1a05', fg='#ffcf66', wraplength=340, justify='left', font=('Segoe UI', 9, 'bold'))
        s.avt.pack(side='left', padx=8, pady=6)
        for t, ok in (('✕ CANCELAR', False), ('✓ CONFIRMAR', True)):
            tk.Button(s.av, text=t, command=lambda ok=ok: confirmar(ok), bg='#3d2708' if ok else '#241403', fg='#ffcf66', activebackground='#ffcf66', activeforeground='#000', relief='flat', font=('Segoe UI', 8, 'bold'), padx=8, pady=3).pack(side='right', padx=3)

        # Barra de Entrada
        f = tk.Frame(dr, bg='#070e16', highlightthickness=1, highlightbackground='#15293b')
        f.pack(fill='x', padx=8, pady=(2, 6), ipady=2)
        s.prompt_icon = tk.Label(f, text=' ❯ ', fg='#00e5ff', bg='#070e16', font=('Consolas', 11, 'bold'))
        s.prompt_icon.pack(side='left', padx=(4, 0))
        s.acc.append((s.prompt_icon, 'fg'))

        s.en = tk.Entry(f, bg='#070e16', fg='#ffffff', insertbackground='#00e5ff', relief='flat', font=('Segoe UI', 10), highlightthickness=0)
        s.en.pack(side='left', fill='x', expand=True, padx=4, ipady=3)
        s.en.bind('<Return>', s.enviar); r.bind('<Control-space>', lambda e: interrumpir()); s.en.focus_set()

        s.btn_env = tk.Button(f, text='> ENVIAR', command=s.enviar, bg='#0369a1', fg='#ffffff', activebackground='#0284c7', activeforeground='#fff', relief='flat', font=('Segoe UI', 8, 'bold'), padx=10, cursor='hand2')
        s.btn_env.pack(side='right', padx=4, pady=2)

        # Botones de Acción en 2 Filas Cápsula (Diseño idéntico al mockup)
        btn_box = tk.Frame(dr, bg='#060a0f')
        btn_box.pack(fill='x', padx=6, pady=(0, 6))

        # Fila 1 (4 cápsulas)
        row1 = tk.Frame(btn_box, bg='#060a0f')
        row1.pack(fill='x', pady=2)
        s.btn_capsule(row1, '📱 CELULAR', s.abrir_celular, '#0c2e38', '#0891b2', '#22d3ee').pack(side='left', fill='x', expand=True, padx=2)
        s.btn_capsule(row1, 'COMANDOS', s.abrir_ayuda, '#172554', '#2563eb', '#93c5fd').pack(side='left', fill='x', expand=True, padx=2)
        s.btn_capsule(row1, 'COLOR', s.color, '#3b0764', '#9333ea', '#f0abfc').pack(side='left', fill='x', expand=True, padx=2)
        s.btn_capsule(row1, 'IMAGEN', s.imagen, '#064e3b', '#059669', '#6ee7b7').pack(side='left', fill='x', expand=True, padx=2)

        # Fila 2 (6 cápsulas compactas)
        row2 = tk.Frame(btn_box, bg='#060a0f')
        row2.pack(fill='x', pady=2)
        s.btn_capsule(row2, 'HABLAR', interrumpir, '#0c4a6e', '#0284c7', '#38bdf8').pack(side='left', fill='x', expand=True, padx=1)
        s.bes = s.btn_capsule(row2, 'ESCUCHA', s.t_escucha, '#450a0a', '#dc2626', '#fca5a5')
        s.bes.pack(side='left', fill='x', expand=True, padx=1)
        s.bvoz = s.btn_capsule(row2, 'VOL', s.t_voz, '#431407', '#ea580c', '#fdba74')
        s.bvoz.pack(side='left', fill='x', expand=True, padx=1)
        s.btn_capsule(row2, 'MICRÓFONO', s.abrir_mic, '#134e4a', '#0d9488', '#5eead4').pack(side='left', fill='x', expand=True, padx=1)
        s.btn_capsule(row2, 'NUEVA', s.nueva, '#14532d', '#16a34a', '#86efac').pack(side='left', fill='x', expand=True, padx=1)
        s.btn_capsule(row2, 'MEMORIA', s.abrir_mem, '#422006', '#ca8a04', '#fde047').pack(side='left', fill='x', expand=True, padx=1)

        s.recolor(); s.dibujar(); s.poll(); s.metricas()
        if os.environ.get('JARVIS_TEST'): r.after(2500, r.destroy)

    def barra(s, p, nom):
        fr = tk.Frame(p, bg='#060a0f')
        fr.pack(side='right', padx=(3, 8))
        lbl_v = tk.Label(fr, text='0%', bg='#060a0f', fg='#38bdf8', font=('Consolas', 8, 'bold'), width=4, anchor='w')
        lbl_v.pack(side='right')
        cv = tk.Canvas(fr, width=65, height=6, bg='#0b151e', highlightthickness=1, highlightbackground='#142533')
        it = cv.create_rectangle(0, 0, 0, 6, outline='', fill=S['color'])
        cv.pack(side='right', padx=(2, 3))
        lbl_n = tk.Label(fr, text=f"{nom} Usage", bg='#060a0f', fg='#64748b', font=('Segoe UI', 8, 'bold'))
        lbl_n.pack(side='right')
        s.acc.append((cv, it))
        return cv, it, lbl_v

    def btn_capsule(s, p, txt, cmd, bg_col, border_col, fg_col):
        b = tk.Button(p, text=txt, command=cmd, bg=bg_col, fg=fg_col, activebackground=border_col, activeforeground='#ffffff', relief='flat', font=('Segoe UI', 7, 'bold'), padx=3, pady=3, cursor='hand2', highlightthickness=1, highlightbackground=border_col)
        b.bind('<Enter>', lambda e, btn=b, bc=border_col: btn.config(bg=bc, fg='#ffffff'))
        b.bind('<Leave>', lambda e, btn=b, bgc=bg_col, fgc=fg_col: btn.config(bg=bgc, fg=fgc))
        return b

    def recolor(s):
        s.col = S['color']
        for item in s.acc:
            w = item[0]
            prop = item[1]
            try:
                if isinstance(prop, int): w.itemconfig(prop, fill=s.col)
                elif prop == 'highlightbackground': w.config(highlightbackground=s.col)
                else: w.config(**{prop: s.col})
            except Exception: pass
        s.log.tag_config('sentra ai', foreground=s.col)

    def add(s, e):
        ahora = datetime.datetime.now().strftime('%H:%M:%S')
        q_map = {
            'tú': ('TÚ', 'tu', '👤 '),
            'tú (móvil)': ('TÚ (MÓVIL)', 'movil', '📱 '),
            'sis': ('SISTEMA', 'sis', '⚡ '),
            'sentra ai': (S['nombre'].upper(), 'sentra ai', '🤖 ')
        }
        nom, tag, icono = q_map.get(e['q'], (e['q'].upper(), 'tu', '• '))
        s.log.config(state='normal')
        s.log.insert('end', f"[{ahora}] {icono}{nom}  ", ('time', tag, 'n'))
        s.log.insert('end', e['t'] + '\n\n', tag)
        s.log.config(state='disabled')
        s.log.see('end')

    def enviar(s, _=None):
        t = s.en.get().strip(); s.en.delete(0, 'end')
        if t: lanzar(t)

    def poll(s):
        while not UIQ.empty(): UIQ.get()()
        for e in EV[s.ult:]: s.add(e)
        s.ult = len(EV)
        if S['color'] != s.col: s.recolor()

        s.nom = CFG.get('nombre', 'Sentra Ai')
        s.tit.config(text=s.nom.upper())
        s.r.title(f"{s.nom} · HUD MARK III")

        # Reloj en vivo
        s.clock_lbl.config(text=datetime.datetime.now().strftime('%H:%M:%S'))

        s.bes.config(text='👂 ESCUCHA: ' + ('ON' if S['escucha'] else 'OFF'))
        s.bvoz.config(text='🔊 VOZ: ' + ('SÍ' if S['voz'] else 'NO'))
        s.lvol.config(text='VOL ✕' if S['mudo'] else f"VOL {S['vol']}%")

        if S['pendiente']:
            s.avt.config(text=f"⚠️ {s.nom} requiere confirmación: {S['pendiente'][0]}")
            if not s.av.winfo_ismapped(): s.av.pack(fill='x', pady=(6, 0))
        elif s.av.winfo_ismapped(): s.av.pack_forget()

        if s.mem_w and s.mem_w.winfo_exists(): s.pint_mem()
        s.r.after(80, s.poll)

    def metricas(s):
        if psutil:
            try:
                cpu_v = psutil.cpu_percent()
                ram_v = psutil.virtual_memory().percent
                cv_c, it_c, lbl_c = s.bcpu
                cv_r, it_r, lbl_r = s.bram
                cv_c.coords(it_c, 0, 0, 65 * cpu_v / 100, 6)
                cv_r.coords(it_r, 0, 0, 65 * ram_v / 100, 6)
                lbl_c.config(text=f"{int(cpu_v)}%")
                lbl_r.config(text=f"{int(ram_v)}%")
            except Exception: pass
        s.r.after(1000, s.metricas)

    def dibujar(s):
        c = s.cv; W, H = c.winfo_width(), c.winfo_height(); c.delete('all')
        if W > 20 and H > 20:
            est = S['estado']
            s.fase += .028 * (3.5 if est == 'pensando' else 1.8 if est == 'hablando' else 1.0)
            obj = {'listo': .07, 'escuchando': .35 + .20 * math.sin(s.fase * 4), 'pensando': .25, 'hablando': .45 + .40 * random.random()}.get(est, .07)
            s.nivel += (obj - s.nivel) * .22
            n, f, col = s.nivel, s.fase, S['color']
            cx, cy = W / 2, H / 2 - 10

            # Proporciones dinámicas de la caja HUD central
            box_w = min(W * 0.76, H * 0.78, 430)
            box_h = box_w * 1.08
            bx1, bx2 = cx - box_w / 2, cx + box_w / 2
            by1, by2 = cy - box_h * 0.46, cy + box_h * 0.54
            cy_r = by1 + box_h * 0.40
            r = box_w * 0.36

            # ----------------------------------------------------
            # 1. PISTAS DE CIRCUITO DE COBRE (STARK PCB COPPER TRACES)
            # ----------------------------------------------------
            C_COP1 = '#c87d46'  # Cobre cálido principal
            C_COP2 = '#e09653'  # Reflejo cobre brillante
            C_COP3 = '#7e421d'  # Cobre oscuro de fondo

            def draw_via(vx, vy):
                c.create_oval(vx - 3, vy - 3, vx + 3, vy + 3, fill=C_COP1, outline=C_COP2, width=1)
                c.create_oval(vx - 1, vy - 1, vx + 1, vy + 1, fill='#04070b', outline='')

            # Pistas lado izquierdo
            t_left = [
                ([(15, cy - 170), (bx1 - 80, cy - 170), (bx1 - 30, cy - 120), (bx1, cy - 120)], C_COP1, 2),
                ([(30, cy - 150), (bx1 - 85, cy - 150), (bx1 - 40, cy - 105), (bx1, cy - 105)], C_COP2, 1),
                ([(10, cy - 130), (bx1 - 90, cy - 130), (bx1 - 50, cy - 90),  (bx1, cy - 90)],  C_COP3, 2),
                ([(40, cy - 110), (bx1 - 95, cy - 110), (bx1 - 65, cy - 80),  (bx1, cy - 80)],  C_COP1, 1),

                ([(15, cy - 25),  (bx1 - 90, cy - 25),  (bx1 - 50, cy + 15),  (bx1, cy + 15)],  C_COP1, 2),
                ([(35, cy - 10),  (bx1 - 80, cy - 10),  (bx1 - 40, cy + 30),  (bx1, cy + 30)],  C_COP2, 1),
                ([(20, cy + 5),   (bx1 - 70, cy + 5),   (bx1 - 30, cy + 45),  (bx1, cy + 45)],  C_COP3, 1),

                ([(25, cy + 85),  (bx1 - 65, cy + 85),  (bx1 - 25, cy + 125), (bx1, cy + 125)], C_COP1, 2),
                ([(45, cy + 105), (bx1 - 55, cy + 105), (bx1 - 15, cy + 145), (bx1, cy + 145)], C_COP2, 1),
                ([(10, cy + 145), (bx1 - 75, cy + 145), (bx1 - 35, cy + 185), (bx1, cy + 185)], C_COP3, 2),

                ([(bx1 + 35, by2), (bx1 + 35, H - 45), (bx1 + 60, H - 20), (cx - 45, H - 20)], C_COP1, 1),
                ([(bx1 + 55, by2), (bx1 + 55, H - 55), (bx1 + 80, H - 30), (cx - 20, H - 30)], C_COP2, 1),
            ]
            for pts, col_t, w_t in t_left:
                flat_pts = [coord for pt in pts for coord in pt]
                c.create_line(*flat_pts, fill=col_t, width=w_t, joinstyle='miter')
                draw_via(pts[0][0], pts[0][1])

            # Pistas lado derecho
            t_right = [
                ([(bx2, cy - 120), (bx2 + 35, cy - 120), (bx2 + 85, cy - 70),  (W - 20, cy - 70)],  C_COP1, 2),
                ([(bx2, cy - 105), (bx2 + 45, cy - 105), (bx2 + 95, cy - 55),  (W - 40, cy - 55)],  C_COP2, 1),
                ([(bx2, cy - 85),  (bx2 + 55, cy - 85),  (bx2 + 105, cy - 35), (W - 15, cy - 35)],  C_COP3, 2),

                ([(bx2, cy + 15),  (bx2 + 40, cy + 15),  (bx2 + 75, cy + 50),  (W - 25, cy + 50)],  C_COP1, 2),
                ([(bx2, cy + 30),  (bx2 + 30, cy + 30),  (bx2 + 65, cy + 65),  (W - 45, cy + 65)],  C_COP2, 1),
                ([(bx2, cy + 50),  (bx2 + 20, cy + 50),  (bx2 + 55, cy + 85),  (W - 10, cy + 85)],  C_COP3, 1),

                ([(bx2, cy + 115), (bx2 + 45, cy + 115), (bx2 + 80, cy + 150), (W - 30, cy + 150)], C_COP1, 2),
                ([(bx2, cy + 135), (bx2 + 55, cy + 135), (bx2 + 90, cy + 170), (W - 50, cy + 170)], C_COP2, 1),

                ([(bx2 - 35, by2), (bx2 - 35, H - 45), (bx2 - 60, H - 20), (cx + 45, H - 20)], C_COP1, 1),
                ([(bx2 - 55, by2), (bx2 - 55, H - 55), (bx2 - 80, H - 30), (cx + 20, H - 30)], C_COP2, 1),
            ]
            for pts, col_t, w_t in t_right:
                flat_pts = [coord for pt in pts for coord in pt]
                c.create_line(*flat_pts, fill=col_t, width=w_t, joinstyle='miter')
                draw_via(pts[-1][0], pts[-1][1])

            # ----------------------------------------------------
            # 2. ANILLO ORBITAL CYAN EXTERIOR TENUE (ORBITAL PARTICLES RING)
            # ----------------------------------------------------
            r_orb = box_w * 0.56
            c.create_oval(cx - r_orb, cy_r - r_orb, cx + r_orb, cy_r + r_orb, outline='#0c2230', dash=(3, 7), width=1)
            for i in range(16):
                ang_p = i * (math.pi / 8) + f * 0.02
                px = cx + r_orb * math.cos(ang_p)
                py = cy_r + r_orb * math.sin(ang_p)
                c.create_oval(px - 1.5, py - 1.5, px + 1.5, py + 1.5, fill='#0284c7', outline='')

            # ----------------------------------------------------
            # 3. CONTENEDOR RECTANGULAR DEL NÚCLEO (STARK HUD FRAME BOX)
            # ----------------------------------------------------
            c.create_rectangle(bx1, by1, bx2, by2, fill='#03070d', outline='#142736', width=2)

            # Soportes en esquina (Corner Brackets cyan)
            brk_len = 14
            c.create_line(bx1, by1 + brk_len, bx1, by1, bx1 + brk_len, by1, fill='#00e5ff', width=2)
            c.create_line(bx2 - brk_len, by1, bx2, by1, bx2, by1 + brk_len, fill='#00e5ff', width=2)
            c.create_line(bx1, by2 - brk_len, bx1, by2, bx1 + brk_len, by2, fill='#00e5ff', width=2)
            c.create_line(bx2 - brk_len, by2, bx2, by2, bx2 - brk_len, by2, fill='#00e5ff', width=2)

            # Marcas de escala perimetrales
            for tick_x in range(int(bx1 + 30), int(bx2 - 25), 35):
                c.create_line(tick_x, by1, tick_x, by1 + 3, fill='#1e3a4f', width=1)
                c.create_line(tick_x, by2 - 3, tick_x, by2, fill='#1e3a4f', width=1)

            # ----------------------------------------------------
            # 4. ANILLO GRADUADO DE MEDICIÓN (RULER TICK RING)
            # ----------------------------------------------------
            r_out = r * 0.98
            c.create_oval(cx - r_out, cy_r - r_out, cx + r_out, cy_r + r_out, outline=mix(col, .22), width=1)

            f_ruler = f * 0.04
            for i in range(84):
                ang = 2 * math.pi * i / 84 + f_ruler
                l_tick = 6 if i % 6 == 0 else 3
                w_tick = 2 if i % 6 == 0 else 1
                c_tick = mix(col, .65 if i % 6 == 0 else .22)
                x1 = cx + (r_out - l_tick) * math.cos(ang)
                y1 = cy_r + (r_out - l_tick) * math.sin(ang)
                x2 = cx + r_out * math.cos(ang)
                y2 = cy_r + r_out * math.sin(ang)
                c.create_line(x1, y1, x2, y2, fill=c_tick, width=w_tick)

            # Soportes curvos Stark exteriores
            r_brk = r * 0.99
            c.create_arc(cx - r_brk, cy_r - r_brk, cx + r_brk, cy_r + r_brk, start=320, extent=75, style='arc', outline=col, width=3)
            c.create_arc(cx - r_brk, cy_r - r_brk, cx + r_brk, cy_r + r_brk, start=140, extent=65, style='arc', outline=mix(col, .60), width=2)
            c.create_arc(cx - r_brk, cy_r - r_brk, cx + r_brk, cy_r + r_brk, start=75, extent=25, style='arc', outline=mix(col, .80), width=2)

            # ----------------------------------------------------
            # 5. ENGRANAJE DENTADO PERIFÉRICO (CRENELLATED GEAR RING)
            # ----------------------------------------------------
            r_gear_in = r * 0.81
            r_gear_out = r * 0.88
            c.create_oval(cx - r_gear_in, cy_r - r_gear_in, cx + r_gear_in, cy_r + r_gear_in, outline=mix(col, .30), width=1)
            c.create_oval(cx - r_gear_out, cy_r - r_gear_out, cx + r_gear_out, cy_r + r_gear_out, outline=mix(col, .40), width=1)

            f_gear = f * 0.08
            for i in range(40):
                ang = 2 * math.pi * i / 40 + f_gear
                gx1 = cx + r_gear_in * math.cos(ang)
                gy1 = cy_r + r_gear_in * math.sin(ang)
                gx2 = cx + r_gear_out * math.cos(ang)
                gy2 = cy_r + r_gear_out * math.sin(ang)
                c.create_line(gx1, gy1, gx2, gy2, fill=mix(col, .45 + .40 * math.sin(i * 0.8 + f * 2)), width=3, capstyle='round')

            # ----------------------------------------------------
            # 6. ARCO ROJO DE ALERTA DE STATUS (10:00 a 12:00)
            # ----------------------------------------------------
            r_red = r * 0.74
            rojo_col = '#ff2828'
            r_red_w = 4 if est in ('pensando', 'hablando') else 3
            c.create_arc(cx - r_red, cy_r - r_red, cx + r_red, cy_r + r_red, start=105, extent=50, style='arc', outline=rojo_col, width=r_red_w)

            ang_red_tip = math.radians(105 + 50)
            rt_x = cx + r_red * math.cos(ang_red_tip)
            rt_y = cy_r - r_red * math.sin(ang_red_tip)
            c.create_oval(rt_x - 3, rt_y - 3, rt_x + 3, rt_y + 3, fill='#ffffff', outline=rojo_col)

            # ----------------------------------------------------
            # 7. PISTAS Y SEGMENTOS CYAN GIRATORIOS (MID SEGMENTED TRACK)
            # ----------------------------------------------------
            r_mid = r * 0.67
            c.create_oval(cx - r_mid, cy_r - r_mid, cx + r_mid, cy_r + r_mid, outline=mix(col, .20), width=1)
            f_mid = -f * 0.06
            c.create_arc(cx - r_mid, cy_r - r_mid, cx + r_mid, cy_r + r_mid, start=f_mid * 57.3 + 10, extent=90, style='arc', outline=col, width=3)
            c.create_arc(cx - r_mid, cy_r - r_mid, cx + r_mid, cy_r + r_mid, start=f_mid * 57.3 + 130, extent=60, style='arc', outline=mix(col, .70), width=2)
            c.create_arc(cx - r_mid, cy_r - r_mid, cx + r_mid, cy_r + r_mid, start=f_mid * 57.3 + 220, extent=100, style='arc', outline=col, width=3)

            r_dots = r * 0.58
            for i in range(32):
                ang = 2 * math.pi * i / 32 + f * 0.04
                px = cx + r_dots * math.cos(ang)
                py = cy_r + r_dots * math.sin(ang)
                c.create_oval(px - 1, py - 1, px + 1, py + 1, fill=mix(col, .40), outline='')

            # ----------------------------------------------------
            # 8. APERTURA DE IRIS SEGMENTADA (3-BLADE IRIS)
            # ----------------------------------------------------
            r_iris_out = r * 0.49
            f_iris = f * 0.14
            for s_idx in range(3):
                ang_ini = s_idx * 120 + f_iris * 57.3
                c.create_arc(cx - r_iris_out, cy_r - r_iris_out, cx + r_iris_out, cy_r + r_iris_out,
                             start=ang_ini + 6, extent=108, style='arc', outline=mix(col, .85), width=max(2, int(r * 0.07)))

            # ----------------------------------------------------
            # 9. ONDAS DE PULSO DE AUDIO REACTIVAS
            # ----------------------------------------------------
            if est in ('hablando', 'escuchando'):
                wave_r = r * (0.35 + ((f * 1.8) % 1.0) * 0.55)
                wave_alpha = max(0.0, 1.0 - ((f * 1.8) % 1.0))
                c.create_oval(cx - wave_r, cy_r - wave_r, cx + wave_r, cy_r + wave_r, outline=mix(col, wave_alpha * 0.7), width=2)

            # ----------------------------------------------------
            # 10. RESPLANDOR RADIAL Y ORBE CENTRAL ESFÉRICO 3D
            # ----------------------------------------------------
            r_core = r * (0.24 + 0.03 * n)

            for k in range(6, 0, -1):
                rr = r_core * (1 + 0.60 * k / 6)
                c.create_oval(cx - rr, cy_r - rr, cx + rr, cy_r + rr, fill=mix(col, (0.05 + 0.25 * n) * (1 - k / 7)), outline='')

            c.create_oval(cx - r_core, cy_r - r_core, cx + r_core, cy_r + r_core, fill=mix(col, 0.45), outline=col, width=2)

            r_inner = r_core * 0.75
            c.create_oval(cx - r_inner, cy_r - r_inner, cx + r_inner, cy_r + r_inner, fill=col, outline='')

            spec_r = r_core * 0.45
            spec_x = cx - r_core * 0.25
            spec_y = cy_r - r_core * 0.25
            c.create_oval(spec_x - spec_r, spec_y - spec_r * 0.65, spec_x + spec_r, spec_y + spec_r * 0.65,
                          fill=mix('#ffffff', 0.85, col), outline='')

            pupil_r = r_core * (0.28 + 0.08 * n)
            c.create_oval(cx - pupil_r, cy_r - pupil_r, cx + pupil_r, cy_r + pupil_r, fill='#ffffff', outline='')

            # ----------------------------------------------------
            # 11. TELEMETRÍA Y ESTADO DENTRO DE LA CAJA (IDÉNTICO AL MOCKUP)
            # ----------------------------------------------------
            c.create_text(cx, by2 - 52, text='• STARK ARC REACTOR // CORE ONLINE •', fill='#3d5d70', font=('Consolas', 7, 'bold'))

            txt_est = {'listo': 'EN LÍNEA', 'escuchando': 'ESCUCHANDO...', 'pensando': 'PROCESANDO...', 'hablando': 'TRANSMITIENDO...'}.get(est, 'EN LÍNEA')
            col_est = {'listo': col, 'escuchando': '#22d3ee', 'pensando': '#f59e0b', 'hablando': '#10b981'}.get(est, col)
            c.create_text(cx, by2 - 30, text=txt_est, fill=col_est, font=('Segoe UI', 13, 'bold'))

            sub_txt = {
                'listo': 'STABLE SYSTEM · ACTIVE CORE · FREQ 432Hz',
                'escuchando': 'VOICE CAPTURE ACTIVE // WHISPER STT',
                'pensando': 'PROCESSING QUERY WITH ' + CFG['modelo'].upper() + '...',
                'hablando': 'TRANSMITTING NEURAL AUDIO STREAM'
            }.get(est, 'STABLE SYSTEM · ACTIVE CORE · FREQ 432Hz')
            c.create_text(cx, by2 - 13, text=sub_txt, fill='#415f70', font=('Consolas', 7))

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
    def abrir_celular(s):
        ip = obtener_ip_local()
        url = f"http://{ip}:{CFG['puerto']}"
        w = s.modal('ACCESO CELULAR', 540, 430)
        tk.Label(w, text='Escanea este código QR desde tu celular para hablar con ' + S['nombre'] + ':', bg=BG, fg=TX, font=('Segoe UI', 10)).pack(pady=(8, 2))
        tk.Label(w, text='(Asegúrate de que el celular esté en el mismo Wi-Fi que la PC)', bg=BG, fg=MUT, font=('Segoe UI', 8)).pack(pady=(0, 4))
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={urllib.parse.quote(url)}"
        try:
            from PIL import ImageTk, Image
            req = urllib.request.Request(qr_url, headers={'User-Agent': 'SentraAI/1.0'})
            img_data = urllib.request.urlopen(req, timeout=4).read()
            img = Image.open(io.BytesIO(img_data))
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(w, image=photo, bg=BG)
            lbl.image = photo
            lbl.pack(pady=4)
        except Exception:
            tk.Label(w, text=f"Abre en el navegador de tu celular:\n{url}", bg=BG, fg=AMB, font=('Segoe UI', 11, 'bold'), wraplength=480).pack(pady=15)
        tk.Label(w, text=f"Dirección IP: {url}", bg=BG, fg=S['color'], font=('Consolas', 10, 'bold')).pack(pady=2)
        tk.Label(w, text="En Firefox para móvil escribe la dirección completa incluyendo http://", bg=BG, fg=MUT, font=('Segoe UI', 8)).pack(pady=(0, 6))
        s.fila(w, ('Abrir en PC', lambda: webbrowser.open(url)), ('Cerrar', w.destroy))
    def cerrar(s): callar(); s.r.destroy()
    def run(s): s.r.mainloop()

if __name__ == '__main__':
    ev('sis', f"{S['nombre']} en línea.")
    ip = iniciar_servidor_movil()
    ev('sis', f"Servidor móvil disponible en: http://{ip}:{CFG['puerto']}")
    try: ms = [m.model for m in ollama.list().models]; ev('sis', 'Modelo listo: ' + CFG['modelo']) if any(m.startswith(CFG['modelo']) for m in ms) else ev('sis', f"Falta el modelo. Ejecuta: ollama pull {CFG['modelo']}")
    except Exception: ev('sis', 'No encuentro Ollama. Instálalo desde ollama.com y ábrelo.')
    if not (sd and WhisperModel): ev('sis', 'Micrófono desactivado: falta sounddevice o faster-whisper.')
    threading.Thread(target=bucle_voz, daemon=True).start(); HUD().run()
