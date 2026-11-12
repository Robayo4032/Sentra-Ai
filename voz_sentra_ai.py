"""voz_sentra_ai.py - voces neuronales gratis de Microsoft (servidores de Edge), con foco en español de Colombia.
Creado por Derek · github.com/DerekAI
Instalar una vez:   pip install edge-tts
Elegir la voz:      python voz_sentra_ai.py      (escuchas cada una, la eliges y queda guardada en voz_sentra_ai.json)
Para usarla en código:  from voz_sentra_ai import hablar, callar;  hablar('Hola, señor')"""
import asyncio, json, os, re, sys, tempfile, subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))
ARCH = os.path.join(AQUI, 'voz_sentra_ai.json')
# Soporte retrocompatible si existía voz_jarvis.json
if not os.path.exists(ARCH) and os.path.exists(os.path.join(AQUI, 'voz_jarvis.json')):
    ARCH = os.path.join(AQUI, 'voz_jarvis.json')

DEF = {'voz': 'es-CO-GonzaloNeural', 'rate': '+0%', 'pitch': '+0Hz'}
FRASE = 'Buenas, señor. Todos los sistemas están en línea. ¿En qué le puedo ayudar hoy?'

def cargar():
    try: return {**DEF, **json.load(open(ARCH, encoding='utf-8'))}
    except Exception: return dict(DEF)

def guardar(c): json.dump(c, open(ARCH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

def _edge():
    try:
        import edge_tts
        return edge_tts
    except ImportError:
        return None

def listar(locales=('es-CO',)):
    """Pide al servidor de Microsoft la lista real de voces y filtra por país."""
    ed = _edge()
    if not ed: return []
    vs = asyncio.run(ed.list_voices())
    return sorted((v for v in vs if v['Locale'] in locales), key=lambda v: (v['Locale'] != 'es-CO', v['ShortName']))

def sintetizar(texto, c=None):
    c = c or cargar(); fd, ruta = tempfile.mkstemp(suffix='.mp3'); os.close(fd)
    ed = _edge()
    if not ed: raise RuntimeError('edge_tts no está instalado')
    asyncio.run(ed.Communicate(texto, c['voz'], rate=c['rate'], pitch=c['pitch']).save(ruta)); return ruta

def _mci(cmd):  # reproductor de Windows que ya viene instalado: no hay que instalar nada más
    import ctypes
    b = ctypes.create_unicode_buffer(255); ctypes.windll.winmm.mciSendStringW(cmd, b, 254, 0); return b.value

def reproducir(ruta):
    _mci('close jv'); _mci(f'open "{ruta}" type mpegvideo alias jv'); _mci('play jv wait'); _mci('close jv')

PS = ("Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
      "$c=New-Object Globalization.CultureInfo 'es-ES';try{$s.SelectVoiceByHints('Male','NotSet',0,$c)}catch{};$s.Speak($env:JTXT)")
_ps_proc = None

def callar():
    global _ps_proc
    try: _mci('stop jv'); _mci('close jv')
    except Exception: pass
    if _ps_proc and _ps_proc.poll() is None:
        try: _ps_proc.kill()
        except Exception: pass

def hablar(texto, c=None):
    global _ps_proc
    callar()
    c = c or cargar()
    ed = _edge()
    if ed:
        ruta = None
        try:
            ruta = sintetizar(texto, c)
            reproducir(ruta)
            return
        except Exception:
            pass
        finally:
            if ruta:
                try: os.remove(ruta)
                except Exception: pass
    if sys.platform == 'win32':
        _ps_proc = subprocess.Popen(['powershell', '-NoProfile', '-Command', PS], env=dict(os.environ, JTXT=texto), creationflags=0x08000000)
        _ps_proc.wait()

def _probar(c, texto=FRASE):
    print('  generando…', end='', flush=True)
    try: hablar(texto, c); print(' listo.')
    except Exception as e: print(f'\n  No pude: {e}')

def menu():
    c = cargar(); print('Conectando con el servidor de voces…')
    try: vs = listar()
    except Exception as e: sys.exit(f'No pude conectar (¿hay internet?): {e}')
    if not vs: sys.exit('El servidor no devolvió voces de Colombia.')
    while True:
        print('\n=== VOCES DE COLOMBIA ===')
        for i, v in enumerate(vs, 1):
            print(f"  {i}) {v['ShortName']}  ({'mujer' if v['Gender'] == 'Female' else 'hombre'})" + ('   <- en uso' if v['ShortName'] == c['voz'] else ''))
        print(f"\nAjustes: velocidad {c['rate']} · tono {c['pitch']}")
        print('Escribe: número = escuchar · u N = usar esa voz · v = velocidad · t = tono · f = frase propia · o = otras voces en español · q = salir')
        x = input('> ').strip().lower()
        if x in ('q', ''): break
        elif x.isdigit() and 1 <= int(x) <= len(vs): _probar({**c, 'voz': vs[int(x) - 1]['ShortName']})
        elif re.fullmatch(r'u\s*\d+', x) and 1 <= int(x[1:]) <= len(vs): c['voz'] = vs[int(x[1:]) - 1]['ShortName']; guardar(c); print('  Guardada:', c['voz']); _probar(c)
        elif x == 'v':
            n = input('  Velocidad en % (ej: +10 más rápida, -10 más lenta, 0 normal): ').strip().replace('%', '')
            if re.fullmatch(r'[+-]?\d{1,3}', n): c['rate'] = f"{int(n):+d}%"; guardar(c); _probar(c)
        elif x == 't':
            n = input('  Tono en Hz (ej: -10 más grave, +10 más agudo, 0 normal): ').strip().replace('Hz', '')
            if re.fullmatch(r'[+-]?\d{1,3}', n): c['pitch'] = f"{int(n):+d}Hz"; guardar(c); _probar(c)
        elif x == 'f': _probar(c, input('  Frase: ').strip() or FRASE)
        elif x == 'o':
            vs = listar(('es-CO', 'es-MX', 'es-ES', 'es-AR', 'es-US', 'es-VE', 'es-PE', 'es-CL'))
    print('Listo. Voz actual:', c['voz'], c['rate'], c['pitch'])

if __name__ == '__main__': menu()
