import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import json
import datetime

# --- CONFIGURACIÓN ---
ANCHO = 40
ALTO = 25

class DiseñadorConectado:
    def __init__(self, ancho, alto, nombre_archivo="escenario_base"):
        self.nombre_archivo_base = nombre_archivo 
        self.ancho = ancho
        self.alto = alto
        
        # Datos
        self.muros = []   
        self.agentes = [] 
        self.hitos = {}   
        self.hitos_bounds = [] 
        
        # Contadores
        self.cont_hab = 1
        self.cont_muro = 1
        self.cont_puerta = 1
        self.cont_salida = 1
        
        # Estado
        # --- NUEVO: Constantes paramétricas (BIM / IndoorGML) ---
        self.GROSORES = {
            'muro_exterior': 0.40, # Muros de carga (gruesos)
            'muro_interior': 0.15, # Tabiques (delgados)
            'puerta': 0.20         # Para operaciones booleanas en el futuro
        }
        # Estado inicial
        self.modo = 'muro_exterior'

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

        self.linea_temp, = self.ax.plot([], [], color='red', linestyle='-', linewidth=1.5, alpha=0.7, zorder=4)
        
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
        # --- AQUÍ AÑADIMOS LOS NUEVOS MODOS ---
        if self.modo in ['muro_exterior', 'muro_interior']:
            tit = f"MODO: {'MURO EXTERIOR (Grueso)' if self.modo == 'muro_exterior' else 'MURO INTERIOR (Delgado)'}"
            # Aquí hemos compactado el texto para que quepan todos los atajos
            instrucciones = "[Clic Izq]: Polilínea (Doble Clic corta) | [Clic Der]: Puerta\n[m/n]: Muros | [a]: Agentes | [h]: Hitos | [s]: Salidas | [z]: Deshacer"
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

    def calcular_esquinas_muro(self, x1, y1, x2, y2, grosor):
        """Calcula los 4 vértices de un rectángulo a partir de una línea central y un grosor."""
        dx = x2 - x1
        dy = y2 - y1
        longitud = np.sqrt(dx**2 + dy**2)
        
        if longitud == 0: 
            return None
        
        # Vector normalizado perpendicular
        nx = -dy / longitud
        ny = dx / longitud
        
        mitad = grosor / 2.0
        
        # Calcular las 4 esquinas expandiendo desde la directriz
        p1 = (x1 + nx * mitad, y1 + ny * mitad)
        p2 = (x1 - nx * mitad, y1 - ny * mitad)
        p3 = (x2 - nx * mitad, y2 - ny * mitad)
        p4 = (x2 + nx * mitad, y2 + ny * mitad)
        
        return [p1, p2, p3, p4]

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

        # Dibujar muros con grosor paramétrico y directriz visible
        for muro in self.muros:
            id_muro, tipo, x1, y1, x2, y2 = muro
            
            if tipo in ['muro_exterior', 'muro_interior']:
                grosor = self.GROSORES[tipo]
                esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, grosor)
                
                if esquinas:
                    # 1. Dibujar el Polígono sólido (Grosor real BIM)
                    color = 'dimgray' if tipo == 'muro_exterior' else 'silver'
                    poligono = patches.Polygon(esquinas, closed=True, facecolor=color, edgecolor='black', alpha=0.9, zorder=2)
                    self.ax.add_patch(poligono)
                    
                    # 2. Dibujar la Directriz (Línea central roja punteada)
                    self.ax.plot([x1, x2], [y1, y2], color='red', linestyle='-', linewidth=1.0, zorder=3)

        # Agentes
        if self.agentes:
            ags = np.array(self.agentes)
            self.ax.scatter(ags[:,0], ags[:,1], c='blue', s=60, zorder=10, edgecolors='white')
        
        self.fig.canvas.draw()

    def es_punto_valido_inicio(self, x, y):
        if x < 0.8 or x > self.ancho - 0.8: return True
        if y < 0.8 or y > self.alto - 0.8: return True
        MARGEN = 0.8 
        for id_muro, tipo, mx1, my1, mx2, my2 in self.muros:
            if mx1 == mx2: # Vertical
                ymin, ymax = min(my1, my2), max(my1, my2)
                if abs(x - mx1) <= MARGEN and (ymin - MARGEN <= y <= ymax + MARGEN): return True
            else: # Horizontal
                xmin, xmax = min(mx1, mx2), max(mx1, mx2)
                if abs(y - my1) <= MARGEN and (xmin - MARGEN <= x <= xmax + MARGEN): return True
        return False

    def on_click(self, event):
        if event.inaxes != self.ax: return
        
        # Snap a 0.5 metros para mayor precisión en CAD y evitar huecos
        x = round(event.xdata * 2) / 2
        y = round(event.ydata * 2) / 2

        if self.modo == 'agentes' and event.button == 1:
            self.agentes.append((x, y))
            self.dibujar_interfaz()

        elif self.modo in ['muro_exterior', 'muro_interior']:
            if self.puntos_temp is None:
                self.puntos_temp = (x, y)
            else:
                x_ini, y_ini = self.puntos_temp
                
                # Tu excelente lógica para forzar líneas rectas (ortogonales)
                if abs(x - x_ini) > abs(y - y_ini): y = y_ini
                else: x = x_ini
                
                # --- TRUCO PARA CORTAR LA POLILÍNEA ---
                # Si haces clic en el mismo sitio donde empezaste, se corta.
                if x == x_ini and y == y_ini:
                    self.puntos_temp = None
                    self.rect_temp.set_width(0)
                    self.linea_temp.set_data([], [])
                    self.dibujar_interfaz()
                    return
                
                if event.button == 1: # Clic Izquierdo = MURO (Exterior o Interior)
                    nombre = f"Muro_{self.cont_muro}"
                    self.muros.append((nombre, self.modo, x_ini, y_ini, x, y))
                    self.cont_muro += 1
                    
                    # --- AQUÍ ESTÁ LA MAGIA DE LA POLILÍNEA ---
                    # En lugar de None, guardamos el final como el nuevo inicio
                    self.puntos_temp = (x, y) 
                    
                else: # Clic Derecho = PUERTA
                    nombre = f"Puerta_{self.cont_puerta}"
                    self.muros.append((nombre, 'puerta', x_ini, y_ini, x, y))
                    
                    # Lo inyectamos automáticamente como Hito
                    x_min, x_max = min(x_ini, x), max(x_ini, x)
                    y_min, y_max = min(y_ini, y), max(y_ini, y)
                    cx, cy = x_min + (x_max - x_min)/2, y_min + (y_max - y_min)/2
                    self.hitos[nombre] = (cx, cy)
                    self.hitos_bounds.append((nombre, x_min, y_min, x_max, y_max))
                    self.cont_puerta += 1
                    print(f"🚪 {nombre} auto-generada y añadida al grafo.")
                    
                    # Al poner una puerta, cortamos la polilínea
                    self.puntos_temp = None
                    self.rect_temp.set_width(0)
                    self.linea_temp.set_data([], [])

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
                    puertas_a_borrar = []
                    for h_nom, (hx, hy) in self.hitos.items():
                        if "Puerta" in h_nom and (x_min <= hx <= x_max) and (y_min <= hy <= y_max):
                            puertas_a_borrar.append(h_nom)
                    for pb in puertas_a_borrar:
                        del self.hitos[pb]
                        self.hitos_bounds = [b for b in self.hitos_bounds if b[0] != pb]
                        print(f"🔄 {pb} convertida en {nombre_final}")
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
                self.linea_temp.set_data([], [])
                self.dibujar_interfaz()
        

    def on_move(self, event):
        if event.inaxes != self.ax or self.puntos_temp is None: return
        x_start, y_start = self.puntos_temp
        
        # Le aplicamos el mismo imán (snap) que al clic
        x_curr = round(event.xdata * 2) / 2
        y_curr = round(event.ydata * 2) / 2

        # AHORA RECONOCE LOS NUEVOS MODOS
        if self.modo in ['muro_exterior', 'muro_interior']:
            if abs(x_curr - x_start) > abs(y_curr - y_start): 
                y_curr = y_start
                xmin, xmax = min(x_start, x_curr), max(x_start, x_curr)
                self.rect_temp.set_bounds(xmin - 0.5, y_start - 0.5, (xmax - xmin) + 1, 1)
            else: 
                x_curr = x_start
                ymin, ymax = min(y_start, y_curr), max(y_start, y_curr)
                self.rect_temp.set_bounds(x_start - 0.5, ymin - 0.5, 1, (ymax - ymin) + 1)
            
            color_previo = 'gray' if self.modo == 'muro_exterior' else 'lightgray'
            self.rect_temp.set_color(color_previo if event.button != 3 else 'cyan')

            self.linea_temp.set_data([x_start, x_curr], [y_start, y_curr])

        elif self.modo == 'hitos' or self.modo == 'salida':
            x_min, x_max = min(x_start, x_curr), max(x_start, x_curr)
            y_min, y_max = min(y_start, y_curr), max(y_start, y_curr)
            w, h = x_max - x_min, y_max - y_min
            self.rect_temp.set_bounds(x_min, y_min, w, h)
            self.rect_temp.set_color('red' if self.modo == 'salida' else 'magenta')
            
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        # --- NUEVOS MODOS DE MUROS ---
        if event.key == 'm': 
            self.modo = 'muro_exterior'
            self.puntos_temp = None
            print("Modo: Muro Exterior (Grueso)")
        elif event.key == 'n': 
            self.modo = 'muro_interior'
            self.puntos_temp = None
            print("Modo: Muro Interior (Delgado)")
            
        # --- MODOS CLÁSICOS ---
        elif event.key == 'a': self.modo = 'agentes'
        elif event.key == 'h': self.modo = 'hitos'
        elif event.key == 's': self.modo = 'salida'
        
        # --- LÓGICA DE DESHACER (ACTUALIZADA) ---
        elif event.key == 'z':
            if self.modo in ['muro_exterior', 'muro_interior'] and self.muros: 
                borrado = self.muros.pop()
                if borrado[1] == 'puerta':
                    nombre_puerta = borrado[0]
                    if nombre_puerta in self.hitos: del self.hitos[nombre_puerta]
                    self.hitos_bounds = [b for b in self.hitos_bounds if b[0] != nombre_puerta]
            elif self.modo == 'agentes' and self.agentes: self.agentes.pop()
            elif (self.modo == 'hitos' or self.modo == 'salida') and self.hitos_bounds:
                borrado = self.hitos_bounds.pop()
                if borrado[0] in self.hitos: del self.hitos[borrado[0]]
            self.puntos_temp = None
            self.rect_temp.set_width(0)
            self.linea_temp.set_data([], [])

        # --- SECCIÓN PARA EXPORTAR ---
        elif event.key == 'e': 
            conexiones = self.calcular_conexiones()
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            nombre_final = f"{self.nombre_archivo_base}_{timestamp}.json"
            self.exportar_json_legacy(conexiones, nombre_final)
            print(f"💾 Guardado rápido completado.")
        
        elif event.key == 'i': 
            conexiones = self.calcular_conexiones()
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            nombre_final = f"{self.nombre_archivo_base}_IndoorGML_{timestamp}.json"
            self.exportar_indoor_gml(conexiones, nombre_final)
            print(f"🌍 Guardado en formato OGC IndoorGML 2.0 completado.")
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
        # 1. Matriz (Ajustada para soportar coordenadas decimales del nuevo CAD)
        mapa_test = np.zeros((self.ancho, self.alto))
        mapa_test[0,:] = 1; mapa_test[-1,:] = 1
        mapa_test[:,0] = 1; mapa_test[:,-1] = 1
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            # Reconocemos los nuevos tipos de muro
            val = 1 if tipo in ['muro_exterior', 'muro_interior'] else 0
            
            # Convertimos a entero (int) para que la matriz Numpy no explote con los decimales 0.5
            ix1, iy1, ix2, iy2 = int(x1), int(y1), int(x2), int(y2)
            
            if ix1 == ix2: mapa_test[ix1, min(iy1,iy2):max(iy1,iy2)+1] = val
            else: mapa_test[min(ix1,ix2):max(ix1,ix2)+1, iy1] = val

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
        nombre_final = f"{self.nombre_archivo_base}_FINAL.json"
        self.exportar_json_legacy(conexiones_detectadas, nombre_final)

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
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            val = 1 if tipo == 'muro' else 0
            if x1 == x2: print(f"        self.mapa_muros[{x1}, {min(y1,y2)}:{max(y1,y2)+1}] = {val}")
            else: print(f"        self.mapa_muros[{min(x1,x2)}:{max(x1,x2)+1}, {y1}] = {val}")
        print("="*60)

    def exportar_json_legacy(self, conexiones, nombre_archivo="escenario_base.json"):
        datos = {
            "configuracion": {
                "ancho": self.ancho,
                "alto": self.alto
            },
            "hitos": self.hitos,
            "conexiones": conexiones,
            "agentesspawn": self.agentes,
            "muros": []
        }
        
        # Procesar los muros para PRE-CALCULAR la geometría (Baking)
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            # 1. Obtener el grosor (usamos 0.10 por defecto si hay algún error)
            grosor = self.GROSORES.get(tipo, 0.10) 
            
            # 2. Calcular los 4 vértices (Polígono 2D)
            esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, grosor)
            
            # 3. Empaquetar en el JSON
            if esquinas:
                datos["muros"].append({
                    "id": id_muro,
                    "tipo": tipo,
                    "poligono": esquinas, # Enviamos el área exacta de colisión
                    "directriz": {        # Mantenemos la línea base por si el simulador quiere dibujarla
                        "x1": min(x1, x2), 
                        "y1": min(y1, y2),
                        "x2": max(x1, x2), 
                        "y2": max(y1, y2)
                    }
                })

        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4)
            
        print(f"\n✅ MAPA GEOMÉTRICO EXPORTADO CORRECTAMENTE A: '{nombre_archivo}'")

    def exportar_indoor_gml(self, conexiones, nombre_archivo="escenario_indoorgml.json"):
        datos_indoorgml = {
            "featureType": "IndoorFeatures",
            "layers": [] # Aquí construiremos el estándar en el futuro
        }
        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos_indoorgml, f, indent=4)

if __name__ == "__main__":
    print("=== CONFIGURACIÓN INICIAL ===")
    nombre_base = input("Introduce el nombre base para tu escenario (ej. 'nivel_1'): ")
    # Si el usuario pulsa Enter sin escribir nada, le damos un nombre por defecto
    if not nombre_base.strip(): 
        nombre_base = "escenario_custom"
        
    # Necesitamos pasarle este nombre a la clase
    app = DiseñadorConectado(ANCHO, ALTO, nombre_base) 
    plt.show()
    app.verificar_visual_y_exportar()