import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

# --- CONFIGURACIÓN ---
ANCHO = 40
ALTO = 25

class DiseñadorConectado:
    def __init__(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        
        # Datos
        self.muros = []   
        self.agentes = [] 
        self.hitos = {}   
        self.hitos_bounds = [] 
        
        # Contadores
        self.cont_hab = 1
        self.cont_puerta = 1
        self.cont_salida = 1
        
        # Estado
        self.modo = 'construccion'
        self.puntos_temp = None    

        # Visual
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        plt.subplots_adjust(bottom=0.15) 
        self.ax.set_aspect('equal')
        self.configurar_lienzo()
        
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_move)
        
        self.rect_temp = patches.Rectangle((0,0), 0, 0, alpha=0.5, color='gray')
        self.ax.add_patch(self.rect_temp)
        
        self.dibujar_interfaz()

    def configurar_lienzo(self):
        self.ax.set_xlim(-1, self.ancho)
        self.ax.set_ylim(-1, self.alto)
        self.ax.set_xticks(np.arange(0, self.ancho, 5))
        self.ax.set_yticks(np.arange(0, self.alto, 5))
        self.ax.set_xticks(np.arange(-0.5, self.ancho, 1), minor=True)
        self.ax.set_yticks(np.arange(-0.5, self.alto, 1), minor=True)
        self.ax.grid(which='minor', color='lightgray', linestyle='-', linewidth=0.5, alpha=0.5)
        self.ax.grid(which='major', color='gray', linestyle='-', linewidth=1, alpha=0.8)
        self.ax.invert_yaxis()

    def actualizar_titulo(self, error=None):
        instrucciones = ""
        color = 'black'
        tit = ""
        if self.modo == 'construccion':
            tit = "MODO: CONSTRUCCIÓN"
            instrucciones = "[Clic Izq]: Muro | [Clic Der]: Puerta\n[a]: Agentes | [h]: Hitos | [s]: Salidas | [z]: Deshacer"
        elif self.modo == 'agentes':
            tit = "MODO: AGENTES"
            color = 'blue'
            instrucciones = "[Clic]: Poner Agente\n[m]: Muros | [h]: Hitos | [s]: Salidas | [z]: Deshacer"
        elif self.modo == 'hitos':
            tit = "MODO: HITOS (Auto-Relleno)"
            color = 'green'
            instrucciones = "Marca Habitaciones o Puertas interiores.\n[m]: Muros | [s]: Salidas | [z]: Deshacer"
        elif self.modo == 'salida':
            tit = "MODO: SALIDAS (Auto-Relleno)"
            color = 'red'
            instrucciones = "Marca las zonas de SALIDA (Deben tocar muro).\n[m]: Muros | [h]: Hitos | [z]: Deshacer"
            
        if error:
            tit = error
            color = 'red'

        self.ax.set_title(tit, color=color, fontweight='bold')
        self.ax.set_xlabel(instrucciones, fontsize=10, backgroundcolor='#f0f0f0')

    def dibujar_interfaz(self, error=None):
        self.ax.clear()
        self.configurar_lienzo()
        self.actualizar_titulo(error)
        self.ax.add_patch(self.rect_temp)
        self.ax.add_patch(plt.Rectangle((-0.5, -0.5), self.ancho, self.alto, fill=False, edgecolor='black', linewidth=2))

        # Hitos
        for nombre, x1, y1, x2, y2 in self.hitos_bounds:
            w, h = x2 - x1, y2 - y1
            
            # Colores según tipo
            if "SALIDA" in nombre: c = 'red'
            elif "Puerta" in nombre: c = 'orange'
            else: c = 'green'
            
            self.ax.add_patch(patches.Rectangle((x1, y1), w, h, linewidth=1, edgecolor=c, facecolor=c, alpha=0.3))
            cx, cy = x1 + w/2, y1 + h/2
            self.ax.text(cx, cy, nombre, ha='center', va='center', fontsize=6, fontweight='bold', bbox=dict(facecolor='white', alpha=0.5, pad=0.1))

        # Muros
        for tipo, x1, y1, x2, y2 in self.muros:
            color = 'black' if tipo == 'muro' else 'cyan'
            alpha = 1.0 if tipo == 'muro' else 0.5
            if x1 == x2: # Vertical
                ymin, ymax = min(y1, y2), max(y1, y2)
                rect = patches.Rectangle((x1 - 0.5, ymin - 0.5), 1, (ymax - ymin) + 1, facecolor=color, alpha=alpha, edgecolor='none')
            else: # Horizontal
                xmin, xmax = min(x1, x2), max(x1, x2)
                rect = patches.Rectangle((xmin - 0.5, y1 - 0.5), (xmax - xmin) + 1, 1, facecolor=color, alpha=alpha, edgecolor='none')
            self.ax.add_patch(rect)

        # Agentes
        if self.agentes:
            ags = np.array(self.agentes)
            self.ax.scatter(ags[:,0], ags[:,1], c='blue', s=60, zorder=10, edgecolors='white')
        
        self.fig.canvas.draw()

    def es_punto_valido_inicio(self, x, y):
        if x < 0.8 or x > self.ancho - 0.8: return True
        if y < 0.8 or y > self.alto - 0.8: return True
        MARGEN = 0.8 
        for tipo, mx1, my1, mx2, my2 in self.muros:
            if mx1 == mx2: # Vertical
                ymin, ymax = min(my1, my2), max(my1, my2)
                if abs(x - mx1) <= MARGEN and (ymin - MARGEN <= y <= ymax + MARGEN): return True
            else: # Horizontal
                xmin, xmax = min(mx1, mx2), max(mx1, mx2)
                if abs(y - my1) <= MARGEN and (xmin - MARGEN <= x <= xmax + MARGEN): return True
        return False

    def on_click(self, event):
        if event.inaxes != self.ax: return
        x = int(round(event.xdata))
        y = int(round(event.ydata))

        if self.modo == 'agentes' and event.button == 1:
            self.agentes.append((x, y))
            self.dibujar_interfaz()

        elif self.modo == 'construccion':
            if self.puntos_temp is None:
                self.puntos_temp = (x, y)
            else:
                x_ini, y_ini = self.puntos_temp
                if abs(x - x_ini) > abs(y - y_ini): y = y_ini
                else: x = x_ini
                tipo = 'muro' if event.button == 1 else 'puerta'
                self.muros.append((tipo, x_ini, y_ini, x, y))
                self.puntos_temp = None
                self.rect_temp.set_width(0)
                self.dibujar_interfaz()

        elif (self.modo == 'hitos' or self.modo == 'salida') and event.button == 1:
            if self.puntos_temp is None:
                if self.es_punto_valido_inicio(x, y):
                    self.puntos_temp = (x, y)
                    self.dibujar_interfaz()
                else:
                    self.dibujar_interfaz(error="⛔ ERROR: INICIA SOBRE UN MURO")
            else:
                x_ini, y_ini = self.puntos_temp
                x_min, x_max = min(x_ini, x), max(x_ini, x)
                y_min, y_max = min(y_ini, y), max(y_ini, y)
                w, h = x_max - x_min, y_max - y_min
                
                # --- AUTO-NAMING ---
                if self.modo == 'salida':
                    nombre_final = f"SALIDA_{self.cont_salida}"
                    self.cont_salida += 1
                else:
                    area = w * h
                    es_puerta = area < 5.0 or (w < 2 or h < 2)
                    if es_puerta:
                        nombre_final = f"Puerta_{self.cont_puerta}"
                        self.cont_puerta += 1
                    else:
                        nombre_final = f"Habitacion_{self.cont_hab}"
                        self.cont_hab += 1
                
                print(f"Zona creada: {nombre_final}")
                cx, cy = x_min + w/2, y_min + h/2
                self.hitos[nombre_final] = (cx, cy)
                self.hitos_bounds.append((nombre_final, x_min, y_min, x_max, y_max))

                self.puntos_temp = None
                self.rect_temp.set_width(0)
                self.dibujar_interfaz()

    def on_move(self, event):
        if event.inaxes != self.ax or self.puntos_temp is None: return
        x_start, y_start = self.puntos_temp
        x_curr = int(round(event.xdata))
        y_curr = int(round(event.ydata))

        if self.modo == 'construccion':
            if abs(x_curr - x_start) > abs(y_curr - y_start): y_curr = y_start; xmin, xmax = min(x_start, x_curr), max(x_start, x_curr); self.rect_temp.set_bounds(xmin - 0.5, y_start - 0.5, (xmax - xmin) + 1, 1)
            else: x_curr = x_start; ymin, ymax = min(y_start, y_curr), max(y_start, y_curr); self.rect_temp.set_bounds(x_start - 0.5, ymin - 0.5, 1, (ymax - ymin) + 1)
            self.rect_temp.set_color('black' if event.button != 3 else 'cyan')

        elif self.modo == 'hitos' or self.modo == 'salida':
            x_min, x_max = min(x_start, x_curr), max(x_start, x_curr)
            y_min, y_max = min(y_start, y_curr), max(y_start, y_curr)
            w, h = x_max - x_min, y_max - y_min
            self.rect_temp.set_bounds(x_min, y_min, w, h)
            self.rect_temp.set_color('red' if self.modo == 'salida' else 'magenta')
            
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        if event.key == 'm': self.modo = 'construccion'
        elif event.key == 'a': self.modo = 'agentes'
        elif event.key == 'h': self.modo = 'hitos'
        elif event.key == 's': self.modo = 'salida'
        elif event.key == 'z':
            if self.modo == 'construccion' and self.muros: self.muros.pop()
            elif self.modo == 'agentes' and self.agentes: self.agentes.pop()
            elif (self.modo == 'hitos' or self.modo == 'salida') and self.hitos_bounds:
                borrado = self.hitos_bounds.pop()
                if borrado[0] in self.hitos: del self.hitos[borrado[0]]
            self.puntos_temp = None
            self.rect_temp.set_width(0)
        self.dibujar_interfaz()

    def calcular_conexiones(self):
        conexiones = []
        BUFFER = 0.6
        nombres = list(self.hitos.keys())
        bounds = {b[0]: b[1:] for b in self.hitos_bounds}
        for i in range(len(nombres)):
            for j in range(i + 1, len(nombres)):
                na, nb = nombres[i], nombres[j]
                ca, cb = self.hitos[na], self.hitos[nb]
                ra, rb = bounds[na], bounds[nb]
                
                # Check A dentro de B o B dentro de A
                conectados = False
                if (rb[0]-BUFFER <= ca[0] <= rb[2]+BUFFER) and (rb[1]-BUFFER <= ca[1] <= rb[3]+BUFFER): conectados = True
                elif (ra[0]-BUFFER <= cb[0] <= ra[2]+BUFFER) and (ra[1]-BUFFER <= cb[1] <= ra[3]+BUFFER): conectados = True
                
                if conectados: conexiones.append((na, nb))
        return conexiones

    def verificar_visual_y_exportar(self):
        # 1. Matriz
        mapa_test = np.zeros((self.ancho, self.alto))
        mapa_test[0,:] = 1; mapa_test[-1,:] = 1
        mapa_test[:,0] = 1; mapa_test[:,-1] = 1
        for tipo, x1, y1, x2, y2 in self.muros:
            val = 1 if tipo == 'muro' else 0
            if x1 == x2: mapa_test[x1, min(y1,y2):max(y1,y2)+1] = val
            else: mapa_test[min(x1,x2):max(x1,x2)+1, y1] = val

        # 2. CALCULAR CONEXIONES
        conexiones_detectadas = self.calcular_conexiones()

        # 3. VISUALIZAR
        plt.figure("VERIFICACIÓN: ¿Ves las líneas amarillas?", figsize=(12, 8))
        plt.imshow(mapa_test.T, cmap='Greys', origin='lower')
        
        # Dibujar Aristas (Conexiones)
        for u, v in conexiones_detectadas:
            p1 = self.hitos[u]
            p2 = self.hitos[v]
            # Linea Amarilla brillante
            plt.plot([p1[0], p2[0]], [p1[1], p2[1]], color='gold', linewidth=2, linestyle='-', zorder=5)

        # Dibujar Nodos (Hitos)
        for nombre, (x, y) in self.hitos.items():
            color_nodo = 'red' if "SALIDA" in nombre else 'green'
            plt.plot(x, y, 'o', color=color_nodo, markeredgecolor='black', zorder=6)
            plt.text(x, y+0.6, nombre, color=color_nodo, ha='center', fontsize=7, fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, pad=0.1), zorder=7)

        if self.agentes:
            ags = np.array(self.agentes)
            plt.scatter(ags[:,0], ags[:,1], c='blue', s=80, edgecolors='white', label='Agentes', zorder=8)
            
        plt.title("MAPA DE CONEXIONES: Habitaciones conectadas mediante líneas amarillas")
        plt.legend(loc='upper right')
        plt.show()
        
        # 4. EXPORTAR
        self.generar_codigo(conexiones_detectadas)

    def generar_codigo(self, conexiones):
        print("\n" + "="*60)
        print("=== CÓDIGO FINAL (CON SALIDAS Y GRAFO) ===")
        print("HITOS = {")
        for k, v in self.hitos.items():
            print(f"    '{k}': ({int(v[0]) if v[0].is_integer() else v[0]}, {int(v[1]) if v[1].is_integer() else v[1]}),")
        print("}")
        print("\n        conexiones = [")
        for u, v in conexiones: print(f"            ('{u}', '{v}'),")
        print("        ]")
        print(f"\n    posiciones_iniciales = {self.agentes}")
        print("\n        self.mapa_muros = np.zeros(({self.ancho}, {self.alto}))")
        print("        self.mapa_muros[0,:] = 1; self.mapa_muros[-1,:] = 1")
        print("        self.mapa_muros[:,0] = 1; self.mapa_muros[:,-1] = 1")
        for tipo, x1, y1, x2, y2 in self.muros:
            val = 1 if tipo == 'muro' else 0
            if x1 == x2: print(f"        self.mapa_muros[{x1}, {min(y1,y2)}:{max(y1,y2)+1}] = {val}")
            else: print(f"        self.mapa_muros[{min(x1,x2)}:{max(x1,x2)+1}, {y1}] = {val}")
        print("="*60)

if __name__ == "__main__":
    app = DiseñadorConectado(ANCHO, ALTO)
    plt.show()
    app.verificar_visual_y_exportar()