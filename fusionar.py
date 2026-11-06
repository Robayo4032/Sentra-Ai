"""Une jarvis.py (el cerebro) con gui_part.py (el HUD en tkinter) y crea jarvis_gui.py.
Uso:  python fusionar.py   (los tres archivos en la misma carpeta)"""
import os, sys
aqui = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(aqui, 'jarvis.py')
gui = os.path.join(aqui, 'gui_part.py')
for f in (src, gui):
    if not os.path.exists(f): sys.exit('Falta el archivo: ' + f)
s = open(src, encoding='utf-8').read()
marca = '# ---------- servidor local'
if marca not in s: sys.exit('Este jarvis.py no tiene la parte del servidor web que esperaba. Pásame tu jarvis.py y lo ajusto.')
s = s[:s.index(marca)]
s = s.replace('from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler\n', '')
s = s.replace('TOKEN = secrets.token_urlsafe(16)\n', '')
s = s.replace('"""JARVIS · asistente local con interfaz HUD. Uso:  python jarvis.py"""',
              '"""JARVIS · asistente local con interfaz HUD propia (tkinter). Uso:  python jarvis_gui.py"""')
out = os.path.join(aqui, 'jarvis_gui.py')
open(out, 'w', encoding='utf-8').write(s + open(gui, encoding='utf-8').read())
print('Listo ->', out)
