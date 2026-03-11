"""
================================================================================
MOTOR DE AUTORÍA Y PROCESAMIENTO ESPACIAL PARA SIMULACIÓN DE MULTITUDES
================================================================================
Descripción: 
Herramienta CAD basada en Python para la generación paramétrica de entornos 
interiores. Implementa Operaciones Booleanas 2D (Shapely) para la extracción 
de mallas de colisión física (CSG) y algoritmos de inferencia topológica para 
la generación automática de Modelos Espaciales Multicapa (MLSM).

Características principales:
- Exportación semántica alineada con el estándar OGC IndoorGML 2.0. (TO BE DONE)
- Extracción de grafos de navegación (Adyacencias, Habitaciones, Door-to-Door).
- Atributos de accesibilidad y locomoción integrados.
================================================================================
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import json
import datetime
import os
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

# --- CONFIGURACIÓN ---
ANCHO = 10
ALTO = 5

class DiseñadorConectado:
    def __init__(self, ancho, alto, nombre_archivo="escenario_base"):
        self.nombre_archivo_base = nombre_archivo 
        self.ancho = ancho
        self.alto = alto
        
        # --- MEMORIA GEOMÉTRICA Y TOPOLÓGICA ---
        self.muros = []        # Lista principal de colisionadores físicos (CSG)
        self.agentes = []      # Spawns iniciales para la simulación
        self.hitos = {}        # Diccionario de nodos matemáticos (Nombre -> Coordenadas X,Y)
        self.hitos_bounds = [] # Guarda el polígono delimitador exacto de cada nodo para el grafo 
        
        # Contadores autoincrementales para nombrar instancias automáticamente
        self.cont_hab = 1
        self.cont_muro = 1
        self.cont_puerta = 1
        self.cont_salida = 1
        
        # --- PARAMETRIZACIÓN BIM (Evitando Magic Numbers) ---
        # Definimos las propiedades físicas del entorno antes de dibujar.
        self.GROSORES = {
            'muro_exterior': 0.40,          # Muros de carga (gruesos)
            'muro_interior': 0.15,          # Tabiques (delgados)
            'puerta_simple': 0.15,
            'puerta_doble': 0.15,
            'salida': 0.20,                 # La salida ahora tiene grosor
            'frontera_virtual': 0.05        # Fina: Actúa como puente topológico, no como obstáculo físico
        }
        
        self.ANCHOS_PUERTA = {'puerta_simple': 0.9, 'puerta_doble': 1.8, 'salida': 2.0}  
        self.RADIO_AGENTE = 0.25 # 50cm de diámetro por defecto

        # --- MÁQUINA DE ESTADOS (STATE MACHINE) ---
        self.modo = 'muro_exterior'      # Herramienta seleccionada actualmente
        self.puntos_temp = None          # Guarda el primer clic (origen de la línea)
        self.puntos_zona_temp = []       # Acumula vértices (clics) para construir polígonos libres
        self.ortogonal = True            # Forzar dibujo en ángulos de 90 grados

        # MAGIA CAD: Variables para la restricción de dibujo de puertas
        self.vector_muro_temp = None     # Guarda el vector direccional del muro donde se pegará la puerta

        # --- MEMORIA SEMÁNTICA (IndoorGML) ---
        self.propiedades_zonas = {}                     # Diccionario: Nombre -> {Atributos IndoorGML}
        self.locomotion_actual = ["Walking", "Rolling"] # Atributo asignado por defecto al dibujar

        # Visual
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        plt.subplots_adjust(bottom=0.15) 
        self.ax.set_aspect('equal')
        self.configurar_lienzo()
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_move)
        # Sombra para hitos (Rectángulo)
        self.rect_temp = patches.Rectangle((0,0), 0, 0, alpha=0.5, color='magenta')
        self.ax.add_patch(self.rect_temp)
        # Sombra para Muros/Puertas (Polígono que soporta diagonales)
        self.poly_temp = patches.Polygon(np.zeros((4,2)), closed=True, alpha=0.5, color='gray')
        self.ax.add_patch(self.poly_temp)
        self.poly_temp.set_visible(False)
        # Línea roja directriz
        self.linea_temp, = self.ax.plot([], [], color='red', linestyle='-', linewidth=1.5, alpha=0.9, zorder=4)
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
        if self.modo.startswith('muro') or self.modo in ['puerta_simple', 'puerta_doble', 'salida', 'frontera_virtual']:
            tit = f"MODO: {self.modo.replace('_', ' ').upper()}"
            instrucciones = "[Clic Izq]: Dibujar | [m/n]: Muros | [p/d]: Puerta | [s]: Salida | [v]: Frontera Virtual | [o]: Ortogonal"
        elif self.modo == 'agentes':
            tit = "MODO: AGENTES"
            color = 'blue'
            instrucciones = "[Clic]: Poner Agente\n[m]: Muros | [h]: Hitos | [s]: Salidas | [z]: Deshacer"
        elif self.modo == 'hitos':
            tit = "MODO: HITOS (Auto-Relleno)"
            color = 'green'
            instrucciones = "Marca vértices de Habitación. [Doble Clic] para cerrar. | [1/2/3]: Locomotion"
        
        if error: tit, color = error, 'red'
        # Mostramos también el atributo IndoorGML actual
        estado_cad = f"Ortogonal: {'ON' if self.ortogonal else 'OFF'}"
        estado_indoor = f"Locomoción: {self.locomotion_actual}"
        self.ax.set_title(f"{tit} | {estado_cad} | {estado_indoor}", color=color, fontweight='bold', fontsize=10)
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
        self.ax.add_patch(self.poly_temp) 
        self.ax.add_line(self.linea_temp)
        self.ax.add_patch(plt.Rectangle((-0.5, -0.5), self.ancho, self.alto, fill=False, edgecolor='black', linewidth=2))


        # Hitos
        # Hitos (Ahora Poligonales)
        for item in self.hitos_bounds:
            if len(item) == 2: # Nos aseguramos de que sea el nuevo formato (nombre, esquinas)
                nombre, coords = item[0], item[1]
                if "Salida" in nombre: c = 'red'
                elif "Puerta" in nombre: c = 'orange'
                else: c = 'green'
                
                poly = patches.Polygon(coords, closed=True, facecolor=c, edgecolor=c, alpha=0.3)
                self.ax.add_patch(poly)
                
                cx, cy = self.hitos[nombre]

                # --- NUEVO: Extraer iniciales de la locomoción (W, R, S) ---
                prop = getattr(self, 'propiedades_zonas', {}).get(nombre, {})
                locs = prop.get("locomotion", [])
                etiqueta_loc = "+".join([l[0] for l in locs]) # Convierte ["Walking", "Rolling"] en "W+R"
                texto_final = f"{nombre}\n[{etiqueta_loc}]" if etiqueta_loc else nombre

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
    
    def obtener_muro_cercano(self, px, py, tolerancia=0.5):
        """
        El 'Imán': Busca si el clic del usuario está cerca de un muro existente.
        Si es así, proyecta el punto matemáticamente sobre la línea del muro para garantizar
        que la puerta empiece exactamente en el eje central de la pared.
        """
        mejor_dist = float('inf')
        mejor_punto = None
        mejor_vector = None
        
        # Iterar sobre todos los muros físicos construidos
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            if tipo.startswith('muro'):
                # Vector del muro (dirección de la pared)
                dx, dy = x2 - x1, y2 - y1
                # Longitud al cuadrado (para optimizar, evitamos la raíz cuadrada aquí)
                l2 = dx*dx + dy*dy 
                if l2 == 0: continue
                
                # Proyección matemática (Dot Product / Producto Escalar)
                # 't' es un porcentaje (de 0 a 1) que indica dónde cae el clic a lo largo del segmento.
                # max(0, min(1, ...)) fuerza a que la proyección no se salga por los extremos del muro.
                t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / l2))
                
                # Coordenadas exactas proyectadas sobre la línea directriz del muro
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                
                # Distancia euclidiana entre el clic del usuario y el punto proyectado
                dist = np.hypot(px - proj_x, py - proj_y)
                
                # Si está dentro de la tolerancia (0.5m), nos quedamos con este muro
                if dist < mejor_dist and dist <= tolerancia:
                    mejor_dist = dist
                    mejor_punto = (proj_x, proj_y)
                    
                    # Normalizamos el vector del muro (longitud = 1) para usarlo luego al arrastrar el ratón
                    length = np.sqrt(l2)
                    mejor_vector = (dx/length, dy/length)

        # Devuelve la coordenada corregida y la dirección del riel del muro              
        if mejor_punto:
            return mejor_punto[0], mejor_punto[1], mejor_vector[0], mejor_vector[1]
        return None

    def on_click(self, event):
        """
        EVENT LOOP (Cierre): Consolida las matemáticas temporales en estructuras de datos permanentes.
        """
        if event.inaxes != self.ax: return
        
        # Snap a 0.5 metros para mayor precisión en CAD y evitar huecos
        x = round(event.xdata * 2) / 2
        y = round(event.ydata * 2) / 2

        if self.modo == 'agentes' and event.button == 1:
            self.agentes.append((x, y))
            self.dibujar_interfaz()

        elif self.modo in ['muro_exterior', 'muro_interior', 'puerta_simple', 'puerta_doble', 'salida', 'frontera_virtual']:
            if self.puntos_temp is None:
                # --- SNAP INICIAL: Obligar a empezar en un muro si es puerta/salida ---
                if self.modo in ['puerta_simple', 'puerta_doble', 'salida']:
                    snap = self.obtener_muro_cercano(x, y)
                    if snap:
                        self.puntos_temp = (snap[0], snap[1])
                        self.vector_muro_temp = (snap[2], snap[3])
                    else:
                        print("⛔ ERROR: Las puertas/salidas deben empezar SOBRE UN MURO.")
                        self.dibujar_interfaz("ERROR: Haz clic sobre un muro")
                else:
                    self.puntos_temp = (x, y) # Muros o fronteras empiezan donde sea
            else:
                x_ini, y_ini = self.puntos_temp
                
                # --- APLICAR RESTRICCIÓN FINAL ---
                if self.modo in ['puerta_simple', 'puerta_doble', 'salida'] and self.vector_muro_temp:
                    vx, vy = self.vector_muro_temp
                    dot = (x - x_ini) * vx + (y - y_ini) * vy
                    signo = 1 if dot >= 0 else -1
                    ancho_real = self.ANCHOS_PUERTA[self.modo]
                    x = x_ini + vx * ancho_real * signo
                    y = y_ini + vy * ancho_real * signo
                elif self.ortogonal:
                    if abs(x - x_ini) > abs(y - y_ini): y = y_ini
                    else: x = x_ini
                
                if x == x_ini and y == y_ini:
                    self.puntos_temp = None; self.poly_temp.set_visible(False); self.linea_temp.set_data([], [])
                    self.dibujar_interfaz(); return
                
                # Guardado de la geometría
                es_puerta = self.modo in ['puerta_simple', 'puerta_doble', 'salida', 'frontera_virtual']
                nombre = f"{self.modo.capitalize()}_{self.cont_puerta if es_puerta else self.cont_muro}"
                
                self.muros.append((nombre, self.modo, x_ini, y_ini, x, y))
                
                if es_puerta:
                    cx, cy = x_ini + (x - x_ini)/2, y_ini + (y - y_ini)/2
                    self.hitos[nombre] = (cx, cy)
                    esquinas_puerta = self.calcular_esquinas_muro(x_ini, y_ini, x, y, self.GROSORES[self.modo])
                    self.hitos_bounds.append((nombre, esquinas_puerta))   
                    
                    # Semántica IndoorGML
                    clase_indoor = "AnchorSpace" if self.modo == 'salida' else "TransferSpace"
                    categoria = "VirtualBoundary" if self.modo == 'frontera_virtual' else ("Transition" if self.modo == 'salida' else "Door")
                    self.propiedades_zonas[nombre] = {"clase_indoor": clase_indoor, "categoria": categoria, "locomotion": self.locomotion_actual}

                    self.cont_puerta += 1
                    self.puntos_temp = None 
                else:
                    self.cont_muro += 1
                    self.puntos_temp = (x, y) 

                self.poly_temp.set_visible(False); self.linea_temp.set_data([], [])
                self.dibujar_interfaz()

        # 1. GENERACIÓN DE HITOS POLIGONALES (Múltiples Clics)
        if (self.modo == 'hitos' or self.modo == 'salida') and event.button == 1:
            # Si el clic actual coincide exactamente con el último clic (Doble Clic), cerramos la forma
            if len(self.puntos_zona_temp) > 0 and x == self.puntos_zona_temp[-1][0] and y == self.puntos_zona_temp[-1][1]:
                if len(self.puntos_zona_temp) >= 3:
                    nombre_final = f"SALIDA_{self.cont_salida}" if self.modo == 'salida' else f"Habitacion_{self.cont_hab}"
                    # --- AQUÍ ESTÁ LA SOLUCIÓN: Sumar 1 a los contadores ---
                    if self.modo == 'salida': 
                        self.cont_salida += 1
                    else: 
                        self.cont_hab += 1
                    # -------------------------------------------------------
                    # MAGIA SHAPELY: Usamos el polígono para calcular el Centro de Masa (Centroide)
                    # Esto asegura que la etiqueta del texto y el nodo del grafo queden perfectamente centrados
                    poly_shapely = ShapelyPolygon(self.puntos_zona_temp)
                    cx, cy = poly_shapely.centroid.x, poly_shapely.centroid.y
                    
                    self.hitos[nombre_final] = (cx, cy)
                    self.hitos_bounds.append((nombre_final, list(self.puntos_zona_temp)))
                    
                    # GUARDADO SEMÁNTICO INDOORGML
                    es_salida = self.modo == 'salida'
                    self.propiedades_zonas[nombre_final] = {
                        "clase_indoor": "AnchorSpace" if es_salida else "NavigableSpace",
                        "categoria": "Transition" if es_salida else "Room",
                        "locomotion": self.locomotion_actual # Herencia del estado global
                    }
                # Resetear memoria temporal para la próxima habitación
                self.puntos_zona_temp = []
                self.poly_temp.set_visible(False)
            else:
                # Si no es doble clic, añadimos el vértice al polígono en construcción
                self.puntos_zona_temp.append((x, y))
                
            self.dibujar_interfaz()
        

    def on_move(self, event):
        """
        EVENT LOOP (Cuerpo): Se ejecuta docenas de veces por segundo al mover el ratón.
        Su función principal es ofrecer Feedback Visual (la "sombra" del muro/puerta) 
        antes de que el usuario haga el clic definitivo.
        """
        # Ignorar si el ratón está fuera del lienzo de dibujo
        if event.inaxes != self.ax: return
        
        # Grid Snapping: Redondea las coordenadas a la media unidad (0.5m) 
        # Esto asegura que los muros encajen en una cuadrícula perfecta, evitando huecos.
        x_curr, y_curr = round(event.xdata * 2) / 2, round(event.ydata * 2) / 2

        # LÓGICA PARA HERRAMIENTAS DE GEOMETRÍA LINEAL (Muros, Puertas, Salidas)
        if self.modo in ['muro_exterior', 'muro_interior', 'puerta_simple', 'puerta_doble', 'salida', 'frontera_virtual']:
            if self.puntos_temp is None: return # Si no hay un primer clic, no hay nada que proyectar
            x_start, y_start = self.puntos_temp
            
            # --- RESTRICCIÓN 1: Bloqueo Magnético (Rail Vector) ---
            # Si estamos dibujando una puerta, forzamos la coordenada actual a proyectarse
            # sobre el vector del muro anfitrión (self.vector_muro_temp).
            if self.modo in ['puerta_simple', 'puerta_doble', 'salida'] and self.vector_muro_temp:
                vx, vy = self.vector_muro_temp
                dot = (x_curr - x_start) * vx + (y_curr - y_start) * vy
                signo = 1 if dot >= 0 else -1
                
                # Anulamos la posición del ratón y forzamos la longitud paramétrica exacta (ej. 0.9m)
                ancho_real = self.ANCHOS_PUERTA[self.modo]
                x_curr = x_start + vx * ancho_real * signo
                y_curr = y_start + vy * ancho_real * signo

            # --- RESTRICCIÓN 2: Modo Ortogonal ---
            # Si no es una puerta (muros libres) y el modo ortogonal está activado ('o'),
            # aplanamos el diferencial menor para forzar ángulos rectos de 90º.
            elif self.ortogonal:
                if abs(x_curr - x_start) > abs(y_curr - y_start): y_curr = y_start
                else: x_curr = x_start

            # --- RENDERIZADO TEMPORAL ---
            # 1. Dibujamos la línea directriz (eje central)
            self.linea_temp.set_data([x_start, x_curr], [y_start, y_curr])
            
            # 2. Extruimos la línea para crear la sombra 2D del polígono
            grosor = self.GROSORES[self.modo]
            esquinas = self.calcular_esquinas_muro(x_start, y_start, x_curr, y_curr, grosor)
            if esquinas:
                self.poly_temp.set_xy(esquinas)
                self.poly_temp.set_visible(True)
                # Color feedback: Naranja para puertas, Gris para muros, Rojo para salidas
                c = 'gray' if self.modo == 'muro_exterior' else 'lightgray'
                if self.modo.startswith('puerta'): c = 'orange'
                elif self.modo == 'salida': c = 'red'
                elif self.modo == 'frontera_virtual': c = 'cyan'
                self.poly_temp.set_color(c)

        # LÓGICA PARA HERRAMIENTAS POLIGONALES LIBRES (Habitaciones)
        elif self.modo in ['hitos', 'salida']:
            # Dibuja la "banda elástica" (Rubber-band) desde el último vértice hasta el ratón actual
            if hasattr(self, 'puntos_zona_temp') and len(self.puntos_zona_temp) > 0:
                last_x, last_y = self.puntos_zona_temp[-1]
                self.linea_temp.set_data([last_x, x_curr], [last_y, y_curr])
                
                # Si tenemos al menos 2 clics, proyectamos cómo quedaría el polígono cerrado
                puntos_dibujo = self.puntos_zona_temp + [(x_curr, y_curr)]
                if len(puntos_dibujo) >= 3:
                    self.poly_temp.set_xy(puntos_dibujo)
                    self.poly_temp.set_visible(True)
                    self.poly_temp.set_color('red' if self.modo == 'salida' else 'green')
                else:
                    self.poly_temp.set_visible(False)
            
        # Pide a Matplotlib que redibuje el frame lo antes posible
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        # --- NUEVOS MODOS DE MUROS ---
        if event.key == 'm': self.modo = 'muro_exterior'; self.puntos_temp = None
        elif event.key == 'n': self.modo = 'muro_interior'; self.puntos_temp = None
        elif event.key == 'p': self.modo = 'puerta_simple'; self.puntos_temp = None
        elif event.key == 'd': self.modo = 'puerta_doble'; self.puntos_temp = None
        elif event.key == 'o': self.ortogonal = not self.ortogonal # Alternar Diagonal    
        # --- MODOS CLÁSICOS ---
        elif event.key == 'a': self.modo = 'agentes'
        elif event.key == 'h': self.modo = 'hitos'
        elif event.key == 's': self.modo = 'salida'; self.puntos_temp = None
        elif event.key == 'v': self.modo = 'frontera_virtual'; self.puntos_temp = None # NUEVA
        # --- NUEVO: Etiquetas de Locomoción IndoorGML ---
        elif event.key == '1': self.locomotion_actual = ["Walking", "Rolling"] # Accesible universal
        elif event.key == '2': self.locomotion_actual = ["Walking"]            # No accesible (ej. terreno irregular)
        elif event.key == '3': self.locomotion_actual = ["Walking", "Step"]    # Escaleras / Desniveles
        # --- LÓGICA DE DESHACER (ACTUALIZADA) ---
        elif event.key == 'z':
            if self.modo.startswith('muro') or self.modo.startswith('puerta'):
                if self.muros:
                    borrado = self.muros.pop()
                    if borrado[1].startswith('puerta') and borrado[0] in self.hitos:
                        del self.hitos[borrado[0]]
                        self.hitos_bounds = [b for b in self.hitos_bounds if b[0] != borrado[0]]
            elif self.modo == 'agentes' and self.agentes: self.agentes.pop()
            elif self.modo in ['hitos', 'salida'] and self.hitos_bounds:
                borrado = self.hitos_bounds.pop()
                if borrado[0] in self.hitos: del self.hitos[borrado[0]]
            self.puntos_temp = None
            self.poly_temp.set_visible(False)
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
        """
        MOTOR DE INFERENCIA TOPOLÓGICA MULTICAPA (MLSM):
        Analiza las distancias y solapamientos de la geometría para inferir 3 grafos distintos.
        Implementa un blindaje anti-esquinas basado en el porcentaje de área interceptada.
        """
        conexiones_enriquecidas = []
        habitaciones = {}
        puertas = {}

        # 1. Clasificación Semántica (Sensible a Mayúsculas/Minúsculas)
        for item in self.hitos_bounds:
            if len(item) == 2:
                nombre, coords = item[0], item[1]
                if len(coords) >= 3:
                    nom_lower = nombre.lower()
                    # Salidas y Fronteras Virtuales se comportan topológicamente como puertas
                    if "puerta" in nom_lower or "salida" in nom_lower or "frontera" in nom_lower:
                        puertas[nombre] = ShapelyPolygon(coords)
                    else:
                        habitaciones[nombre] = ShapelyPolygon(coords)

        # 2. GRAFO MESO: Navegabilidad (Habitación <-> Puerta/Frontera/Salida)
        for nom_hab, poly_hab in habitaciones.items():
            hab_inflada = poly_hab.buffer(0.15) # Inflamos 15cm la habitación para que "toque" la pared
            for nom_pta, poly_pta in puertas.items():
                interseccion = hab_inflada.intersection(poly_pta)
                
                # FILTRO RELATIVO ANTI-ESQUINAS:
                # El solapamiento debe cubrir al menos el 30% del área total de la puerta.
                # Esto evita que una frontera virtual exterior conecte por error rozando una esquina.
                if interseccion.area > (poly_pta.area * 0.30):
                    conexiones_enriquecidas.append({
                        "origen": nom_hab, "destino": nom_pta, 
                        "tipo": "navegable_puerta", "color": "cyan", "estilo": "-"
                    })

        # 3. GRAFO MICRO (Door-to-Door): Navegación avanzada intraroom
        for nom_hab, poly_hab in habitaciones.items():
            hab_inflada = poly_hab.buffer(0.15)
            
            # Filtramos qué puertas pertenecen realmente a esta habitación usando la regla del 30%
            puertas_en_hab = []
            for nom_pta, poly_pta in puertas.items():
                interseccion = hab_inflada.intersection(poly_pta)
                if interseccion.area > (poly_pta.area * 0.30):
                    puertas_en_hab.append(nom_pta)
            
            # Permutación completa: Conectamos todas las puertas de la habitación entre sí
            for i in range(len(puertas_en_hab)):
                for j in range(i + 1, len(puertas_en_hab)):
                    conexiones_enriquecidas.append({
                        "origen": puertas_en_hab[i], "destino": puertas_en_hab[j], 
                        "tipo": "door_to_door", "contexto": nom_hab, "color": "magenta", "estilo": ":"
                    })

        # 4. GRAFO MACRO (Adyacencias Físicas): Navegación de alto nivel (Habitación <-> Habitación)
        nombres_hab = list(habitaciones.keys())
        for i in range(len(nombres_hab)):
            for j in range(i + 1, len(nombres_hab)):
                poly_a = habitaciones[nombres_hab[i]]
                poly_b = habitaciones[nombres_hab[j]]
                
                interseccion = poly_a.buffer(0.15).intersection(poly_b)
                # Filtro Absoluto: Exigimos un área > 0.05m² para asegurar que comparten un segmento de muro real
                if interseccion.area > 0.05:
                    conexiones_enriquecidas.append({
                        "origen": nombres_hab[i], "destino": nombres_hab[j], 
                        "tipo": "adyacencia_fisica", "color": "gold", "estilo": "--"
                    })

        return conexiones_enriquecidas
    
    def procesar_geometria_booleana(self):
        """
        MOTOR CSG (Geometría Constructiva de Sólidos):
        Usa la librería matemática Shapely para restar el volumen físico de las puertas 
        a los muros sólidos. Esto evita que los agentes colisionen con paredes invisibles 
        al intentar cruzar un umbral.
        """
        poligonos_puertas = []
        datos_puertas = []
        
        # 1. Agrupación de Geometría Sustractiva (Las "Herramientas de Corte")
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            if tipo.startswith('puerta'):
                grosor = self.GROSORES[tipo]
                esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, grosor)
                if esquinas:
                    poly = ShapelyPolygon(esquinas)
                    poligonos_puertas.append(poly)
                    datos_puertas.append((id_muro, tipo, esquinas))
                    
        # unary_union fusiona todas las puertas superpuestas en un único "Súper-Polígono"
        # Optimizando masivamente la operación matemática de resta posterior.
        todas_las_puertas = unary_union(poligonos_puertas) if poligonos_puertas else ShapelyPolygon()
        
        muros_recortados = []
        
        # 2. Recorte del Sólido Base (Muros)
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            if tipo.startswith('puerta'): continue # Ignoramos las puertas, ya las usamos para cortar
            
            grosor = self.GROSORES[tipo]
            esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, grosor)
            if not esquinas: continue
            
            poly_muro = ShapelyPolygon(esquinas)
            
            # MAGIA SHAPELY: Operación de Diferencia Booleana (Muro - Puertas)
            muro_final = poly_muro.difference(todas_las_puertas)
            
            if muro_final.is_empty: continue # El muro fue borrado por completo por una puerta enorme
            
            # Gestión de Fragmentación: Si una puerta parte un muro exactamente por la mitad,
            # Shapely devuelve un 'MultiPolygon' (dos trozos desconectados).
            geometrias = muro_final.geoms if hasattr(muro_final, 'geoms') else [muro_final]
            
            for i, geom in enumerate(geometrias):
                # Extraemos las coordenadas matemáticas resultantes y quitamos el último punto 
                # (redundante) para que el formato GeoJSON/Simulador lo procese correctamente.
                coords = list(geom.exterior.coords)[:-1] 
                muros_recortados.append((f"{id_muro}_part{i}", tipo, coords))
                
        return muros_recortados, datos_puertas

    def verificar_visual_y_exportar(self):
        """
        PANTALLA DE VALIDACIÓN FINAL:
        Renderiza el resultado exacto de las operaciones CSG y topológicas antes 
        de empaquetarlas, permitiendo al usuario auditar el modelo matemáticamente.
        """
        conexiones_detectadas = self.calcular_conexiones()
        muros_recortados, datos_puertas = self.procesar_geometria_booleana()

        plt.figure("VERIFICACIÓN GEOMÉTRICA EXACTA (SHAPELY)", figsize=(12, 8))
        ax = plt.gca()
        ax.set_aspect('equal')
        ax.set_xlim(-1, self.ancho)
        ax.set_ylim(-1, self.alto)
        ax.invert_yaxis()
        
        # 1. Dibujar Muros Recortados (CSG Validado)
        for id_muro, tipo, coords in muros_recortados:
            c = 'dimgray' if tipo == 'muro_exterior' else 'silver'
            poly = patches.Polygon(coords, closed=True, facecolor=c, edgecolor='black', alpha=0.9)
            ax.add_patch(poly)
            
        # 2. Dibujar Puertas
        for id_puerta, tipo, coords in datos_puertas:
            poly = patches.Polygon(coords, closed=True, facecolor='orange', edgecolor='black', alpha=0.6)
            ax.add_patch(poly)

        # 3. Dibujar Grafos Topológicos Múltiples (MLSM)
        for conn in conexiones_detectadas:
            u, v = conn["origen"], conn["destino"]
            if u in self.hitos and v in self.hitos:
                p1, p2 = self.hitos[u], self.hitos[v]
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 
                        color=conn["color"], linewidth=2, linestyle=conn["estilo"], zorder=5)
                        
        # 4. Dibujar Nodos y Etiquetas Semánticas
        for nombre, (x, y) in self.hitos.items():
            color_nodo = 'red' if "Salida" in nombre else 'green'
            ax.plot(x, y, 'o', color=color_nodo, markeredgecolor='black', zorder=6)
            
            # Extracción de iniciales de locomoción (Ej: [W+R])
            prop = getattr(self, 'propiedades_zonas', {}).get(nombre, {})
            locs = prop.get("locomotion", [])
            etiqueta_loc = "+".join([l[0] for l in locs])
            texto_final = f"{nombre}\n[{etiqueta_loc}]" if etiqueta_loc else nombre
            ax.text(x, y, texto_final, ha='center', va='center', fontsize=6, fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, pad=0.2))
                
        # 5. Dibujar Agentes (Validación de Escala Física)
        if self.agentes:
            for ax_ag, ay_ag in self.agentes:
                ax.add_patch(patches.Circle((ax_ag, ay_ag), self.RADIO_AGENTE, facecolor='blue', edgecolor='white', zorder=8))
            
        plt.title("MAPA GEOMÉTRICO (Muros CSG y Topología MLSM)")
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.show() # Pausa la ejecución hasta que el usuario cierra la ventana
        
        # EXPORTACIÓN AUTOMÁTICA AL CERRAR
        nombre_final = f"{self.nombre_archivo_base}_FINAL.json"
        self.exportar_mlsm_core(conexiones_detectadas, nombre_final)

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

    def exportar_mlsm_core(self, conexiones, nombre_archivo="escenario_mlsm.json"):
        """
        SERIALIZADOR DE DATOS:
        Empaqueta la geometría, topología y semántica en un perfil JSON híbrido 
        (MLSM Core) optimizado para el motor de simulación.
        """
        muros_recortados, datos_puertas = self.procesar_geometria_booleana()
        
        # Estructura base del contrato de datos
        datos = {
            "configuracion": {"ancho": self.ancho, "alto": self.alto},
            "conexiones_horizontales": conexiones,
            "conexiones_verticales": [], # InterLayerConnections (MLSM)
            "agentesspawn": self.agentes,
            "espacios_navegables": {}, 
            "muros": []
        }
        
        # 1. Empaquetar los Espacios Navegables y Generar Conexiones Verticales
        for nombre, bounds in self.hitos_bounds:
            poligono_coords = bounds[1] if len(bounds) == 2 else bounds
                
            datos["espacios_navegables"][nombre] = {
                "centroide": self.hitos.get(nombre, [0,0]),
                "poligono": poligono_coords,
                "atributos": self.propiedades_zonas.get(nombre, {})
            }
            
            # MAGIA MLSM: Generación dinámica de InterLayerConnections
            clase = self.propiedades_zonas.get(nombre, {}).get("clase_indoor", "")
            
            # Si es habitación, existe en la Capa Macro y Meso simultáneamente
            if clase == "NavigableSpace":
                datos["conexiones_verticales"].append({
                    "nodo_id": nombre,
                    "capa_superior": "adyacencia_fisica",
                    "capa_inferior": "navegable_puerta",
                    "tipo_conexion": "representa_el_mismo_espacio"
                })
            # Si es zona de tránsito, existe en la Capa Meso y Micro
            elif clase in ["TransferSpace", "AnchorSpace"]:
                datos["conexiones_verticales"].append({
                    "nodo_id": nombre,
                    "capa_superior": "navegable_puerta",
                    "capa_inferior": "door_to_door",
                    "tipo_conexion": "representa_el_mismo_espacio"
                })
        
        # 2. Empaquetar Geometría CSG (Muros listos para instanciar Colliders)
        for id_muro, tipo, coords in muros_recortados:
            datos["muros"].append({"id": id_muro, "tipo": tipo, "poligono": coords})
            
        for id_puerta, tipo, coords in datos_puertas:
            datos["muros"].append({"id": id_puerta, "tipo": tipo, "poligono": coords})

        # 3. Enrutamiento del File System Absoluto
        # __file__ obtiene la ruta exacta de este script (MLSM_SpatialEngine.py)
        directorio_script = os.path.dirname(os.path.abspath(__file__))
        carpeta_destino = os.path.join(directorio_script, "escenarios")
        
        os.makedirs(carpeta_destino, exist_ok=True) 
        ruta_completa = os.path.join(carpeta_destino, nombre_archivo)

        # Escritura en disco
        with open(ruta_completa, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4)
            
        print(f"\n✅ PERFIL MLSM CORE EXPORTADO A: '{ruta_completa}'")

    def exportar_indoor_gml(self, conexiones, nombre_archivo="escenario_indoorgml.json"):
        datos_indoorgml = {
            "featureType": "IndoorFeatures",
            "layers": [] # Aquí construiremos el estándar en el futuro
        }
        
        carpeta_destino = "escenarios"
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_completa = os.path.join(carpeta_destino, nombre_archivo)
        
        with open(ruta_completa, 'w', encoding='utf-8') as f:
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