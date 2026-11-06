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
        s.tit = tk.Label(h, bg=BG, font=('Segoe UI', 20, 'bold')); s.tit.pack(side='left'); s.acc.append((s.tit, 'fg'))
        tk.Label(h, text='MARK 5', bg=BG, fg=AMB, font=('Segoe UI', 8), padx=6, highlightbackground=AMB, highlightthickness=1).pack(side='left', padx=12)
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
        s.log.tag_config('jarvis', foreground=s.col)
    def add(s, e):
        q = {'tú': ('Tú', 'tu'), 'sis': ('Sistema', 'sis'), 'jarvis': (S['nombre'], 'jarvis')}[e['q']]
        s.log.config(state='normal'); s.log.insert('end', q[0] + ' · ', ('n', q[1])); s.log.insert('end', e['t'] + '\n\n', q[1]); s.log.config(state='disabled'); s.log.see('end')
    def enviar(s, _=None):
        t = s.en.get().strip(); s.en.delete(0, 'end')
        if t: lanzar(t)
    def poll(s):
        while not UIQ.empty(): UIQ.get()()
        for e in EV[s.ult:]: s.add(e)
        s.ult = len(EV)
        if S['color'] != s.col: s.recolor()
        if S['nombre'] != s.nom: s.nom = S['nombre']; s.tit.config(text='  '.join(s.nom)); s.r.title(s.nom)
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
