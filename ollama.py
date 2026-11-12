"""ollama.py (versión NUBE) - reemplaza al módulo 'ollama' para que Sentra AI use un modelo gratis y rápido en internet.
Creado por Derek · github.com/DerekAI
Ponlo en la MISMA carpeta que sentra_ai_gui.py. No hay que cambiar nada más ni instalar nada.
Sirve con claves de Groq (gsk_...), Google Gemini (AIza...) o Cerebras (csk_...). Detecta solo el proveedor y el modelo."""
import os, sys, json, time, urllib.request, urllib.error

AQUI = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CLAVE = os.path.join(AQUI, 'api_key.txt')
PROV = {  # prefijo de la clave: (nombre, url base, modelos preferidos en orden, modelo con visión)
    'gsk_':  ('Groq', 'https://api.groq.com/openai/v1', ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'], ['llama-4-scout', 'vision']),
    'AIza':  ('Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.0-flash'], ['gemini']),
    'csk-':  ('Cerebras', 'https://api.cerebras.ai/v1', ['llama-3.3-70b', 'gpt-oss-120b', 'llama3.1-8b'], []),
    'csk_':  ('Cerebras', 'https://api.cerebras.ai/v1', ['llama-3.3-70b', 'gpt-oss-120b', 'llama3.1-8b'], []),
}
_estado = {'key': None, 'modelos': None, 'elegido': None}

class R(dict):
    """Diccionario con acceso por atributo (r.message.content y r['message']['content'] funcionan)."""
    def __getattr__(s, k):
        try: return s[k]
        except KeyError: raise AttributeError(k)
    __setattr__ = dict.__setitem__

def _leer_clave():
    k = os.environ.get('JARVIS_API_KEY') or os.environ.get('GROQ_API_KEY') or os.environ.get('GEMINI_API_KEY') or os.environ.get('CEREBRAS_API_KEY')
    if not k and os.path.exists(ARCHIVO_CLAVE):
        l = [x.strip() for x in open(ARCHIVO_CLAVE, encoding='utf-8').read().splitlines() if x.strip()]
        if l: k = l[0]; _estado['modelo_fijo'] = l[1] if len(l) > 1 else None
    return k

def _pedir_clave():
    try:
        import tkinter as tk
        from tkinter import simpledialog
        r = tk.Tk(); r.withdraw()
        k = simpledialog.askstring('JARVIS', 'Pega tu API key (Groq gsk_..., Gemini AIza... o Cerebras csk-...):', show='*', parent=r)
        r.destroy()
        if k and k.strip(): open(ARCHIVO_CLAVE, 'w', encoding='utf-8').write(k.strip() + '\n'); return k.strip()
    except Exception: pass
    return None

def _proveedor():
    k = _estado['key']
    for pre, p in PROV.items():
        if k and k.startswith(pre): return p
    raise RuntimeError('No reconozco esa API key. Debe empezar por gsk_ (Groq), AIza (Gemini) o csk- (Cerebras).')

def _http(ruta, datos=None, reintentos=2):
    nombre, base, _, _ = _proveedor()
    base = os.environ.get('NUBE_URL', base)
    for i in range(reintentos + 1):
        req = urllib.request.Request(base + ruta, data=None if datos is None else json.dumps(datos).encode(), headers={'Authorization': 'Bearer ' + _estado['key'], 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0 JARVIS'})
        try:
            with urllib.request.urlopen(req, timeout=60) as f: return json.loads(f.read().decode())
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode('utf-8', 'ignore')[:400]
            if e.code == 429 and i < reintentos: time.sleep(min(float(e.headers.get('retry-after', 3) or 3), 8)); continue
            if e.code == 400 and 'tool' in cuerpo.lower() and i < reintentos: continue  # el modelo falló al formar la herramienta: reintenta
            if e.code in (401, 403): raise RuntimeError(f'{nombre} rechazó la API key (¿está bien copiada? Bórrala en api_key.txt y pon otra).')
            if e.code == 429: raise RuntimeError(f'{nombre}: llegaste al límite gratis por ahora. Espera un minuto.')
            raise RuntimeError(f'{nombre} error {e.code}: {cuerpo}')
        except urllib.error.URLError as e: raise RuntimeError('No hay conexión a internet con ' + nombre + ': ' + str(e.reason))

def _iniciar():
    if not _estado['key']: _estado['key'] = _leer_clave() or _pedir_clave()
    if not _estado['key']: raise RuntimeError('Falta la API key. Pégala en api_key.txt (junto a jarvis.py).')

def _modelos():
    if _estado['modelos'] is None:
        try: _estado['modelos'] = [m['id'].replace('models/', '') for m in _http('/models').get('data', [])]
        except Exception: _estado['modelos'] = []
    return _estado['modelos']

def _elegir(vision=False):
    _iniciar(); _, _, pref, vis = _proveedor(); ms = _modelos()
    if vision:
        for v in vis:
            for m in ms:
                if v in m.lower(): return m
    if _estado.get('modelo_fijo') and not vision: return _estado['modelo_fijo']
    for p in pref:
        for m in ms:
            if m.lower() == p: return m
    util = [m for m in ms if not any(x in m.lower() for x in ('whisper', 'guard', 'tts', 'embed', 'orpheus', 'playai', 'vision-preview'))]
    return util[0] if util else pref[0]

def _d(x):  # objeto o dict -> dict
    if isinstance(x, dict): return x
    return {k: getattr(x, k) for k in ('role', 'content', 'images', 'tool_calls', 'tool_name', 'name', 'arguments', 'function') if getattr(x, k, None) is not None}

def _convertir(msgs):
    out, pend, n = [], [], 0
    for m in msgs:
        m = _d(m); rol = m.get('role', 'user'); c = m.get('content') or ''
        if rol == 'assistant' and m.get('tool_calls'):
            tcs = []
            for t in m['tool_calls']:
                t = _d(t); f = _d(t.get('function')); a = f.get('arguments', {})
                n += 1; i = f'call_{n}'; pend.append(i)
                tcs.append({'id': i, 'type': 'function', 'function': {'name': f.get('name'), 'arguments': a if isinstance(a, str) else json.dumps(a, ensure_ascii=False)}})
            out.append({'role': 'assistant', 'content': c, 'tool_calls': tcs})
        elif rol == 'tool':
            n += 1; out.append({'role': 'tool', 'tool_call_id': pend.pop(0) if pend else f'call_x{n}', 'content': c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)})
        elif m.get('images'):
            out.append({'role': rol, 'content': [{'type': 'text', 'text': c}] + [{'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + (i if isinstance(i, str) else '')}} for i in m['images']]})
        else: out.append({'role': rol, 'content': c})
    return out

def _herramientas(tools):
    import inspect
    r = []
    for t in tools or []:
        if callable(t):
            ps = {k: {'type': 'string'} for k in inspect.signature(t).parameters}
            r.append({'type': 'function', 'function': {'name': t.__name__, 'description': (t.__doc__ or t.__name__).strip(), 'parameters': {'type': 'object', 'properties': ps, 'required': [*ps]}}})
        else: r.append(t)
    return r

def chat(model=None, messages=(), tools=None, stream=False, **kw):
    _iniciar(); msgs = [*messages]
    vision = any(_d(m).get('images') for m in msgs)
    cuerpo = {'model': _elegir(vision), 'messages': _convertir(msgs), 'temperature': 0.3}
    th = _herramientas(tools)
    if th and not vision: cuerpo['tools'] = th; cuerpo['tool_choice'] = 'auto'
    if kw.get('format') == 'json': cuerpo['response_format'] = {'type': 'json_object'}
    j = _http('/chat/completions', cuerpo)['choices'][0]['message']
    tcs = []
    for t in j.get('tool_calls') or []:
        a = t['function'].get('arguments') or '{}'
        try: a = json.loads(a) if isinstance(a, str) else a
        except Exception: a = {}
        tcs.append(R(function=R(name=t['function']['name'], arguments=a if isinstance(a, dict) else {})))
    r = R(message=R(role='assistant', content=j.get('content') or '', tool_calls=tcs or None), done=True)
    return iter([r]) if stream else r

def _modelo_config():
    try: return json.load(open(os.path.join(AQUI, 'config.json'), encoding='utf-8')).get('modelo') or 'nube'
    except Exception: return 'nube'

def list(*a, **k): return R(models=[R(model=_modelo_config(), name=_modelo_config())])
def __getattr__(nombre): return lambda *a, **k: R()  # pull, show, ps... no hacen falta con la nube

def _ajustar_config():  # un whisper grande es lento: lo baja a 'base' si hace falta
    p = os.path.join(AQUI, 'config.json')
    try:
        c = json.load(open(p, encoding='utf-8'))
        if c.get('whisper') in ('small', 'medium', 'large', 'large-v2', 'large-v3'): c['whisper'] = 'base'; json.dump(c, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except Exception: pass

_estado['key'] = _leer_clave()
if not _estado['key'] and os.environ.get('JARVIS_TEST') is None: _estado['key'] = _pedir_clave()
_ajustar_config()
