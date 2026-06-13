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
from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint, LineString as ShapelyLineString
from shapely.ops import unary_union

# --- CONFIGURACIÓN ---
ANCHO = 15
ALTO = 10

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
        # Aclaracion conceptual: self.muros contiene elementos de autoria lineal
        # (muros, puertas, salidas y fronteras virtuales), no solo muros solidos.
        # self.hitos_bounds contiene footprints/poligonos de espacios, no boundaries MLSM/IndoorGML.
        # self.agentes contiene spawns geometricos, no agentes simulados completos.
        
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

    def get_authoring_elements(self):
        return self.muros

    def get_space_centroids(self):
        return self.hitos

    def get_space_footprints(self):
        return self.hitos_bounds

    def get_space_attributes(self):
        return self.propiedades_zonas

    def get_agent_spawns(self):
        return self.agentes

    def is_wall_type(self, tipo):
        return tipo in ["muro_exterior", "muro_interior"]

    def is_door_type(self, tipo):
        return tipo in ["puerta_simple", "puerta_doble"]

    def is_exit_type(self, tipo):
        return tipo == "salida"

    def is_virtual_boundary_type(self, tipo):
        return tipo == "frontera_virtual"

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

    def _v2_point(self, x, y):
        return {"type": "Point", "coordinates": [float(x), float(y)]}

    def _v2_linestring(self, coords):
        return {
            "type": "LineString",
            "coordinates": [[float(x), float(y)] for x, y in coords]
        }

    def _v2_polygon(self, coords):
        ring = [[float(x), float(y)] for x, y in coords]
        if ring and ring[0] != ring[-1]:
            ring.append(list(ring[0]))
        return {"type": "Polygon", "coordinates": [ring]}

    def _v2_normalizar_id(self, prefix, nombre):
        texto = str(nombre).strip().upper()
        normalizado = []
        for char in texto:
            normalizado.append(char if char.isalnum() else "_")
        compacto = "_".join(parte for parte in "".join(normalizado).split("_") if parte)
        return f"{prefix}_{compacto}" if compacto else prefix

    def _v2_locomotion(self, valores):
        mapping = {"Walking": "walking", "Rolling": "rolling", "Step": "step"}
        normalizados = []
        for valor in valores or []:
            normalizado = mapping.get(valor, str(valor).strip().lower())
            if normalizado and normalizado not in normalizados:
                normalizados.append(normalizado)
        return normalizados

    def _v2_is_exit_name(self, nombre):
        return "salida" in str(nombre).lower()

    def _v2_is_virtual_name(self, nombre):
        return "frontera" in str(nombre).lower()

    def _v2_is_door_name(self, nombre):
        lower = str(nombre).lower()
        return "puerta" in lower or self._v2_is_exit_name(nombre)

    def _v2_space_type_and_category(self, nombre, atributos):
        lower = str(nombre).lower()
        clase = atributos.get("clase_indoor", "")
        categoria_original = str(atributos.get("categoria", "")).lower()

        if "salida" in lower:
            return "exit_space", "exit", "ExitSpace"
        if "frontera" in lower:
            return "transfer_space", "virtual_boundary", "VirtualBoundary"
        if "puerta" in lower or categoria_original == "door":
            return "transfer_space", "door_space", "ConnectionSpace"
        if clase == "TransferSpace":
            return "transfer_space", categoria_original or "transfer_space", "ConnectionSpace"
        if clase == "AnchorSpace":
            return "exit_space", "exit", "ExitSpace"
        return "navigable_space", categoria_original or "room", "General"

    def _v2_catalogs(self):
        return {
            "wall_types": [
                {
                    "catalog_id": "WALL_EXTERIOR_40CM",
                    "element_type": "wall",
                    "wall_type": "exterior",
                    "default_thickness_m": self.GROSORES["muro_exterior"],
                    "default_height_m": 3.0,
                    "default_material": "generic",
                    "description": "Muro exterior exportado desde SpatialEngine"
                },
                {
                    "catalog_id": "WALL_INTERIOR_15CM",
                    "element_type": "wall",
                    "wall_type": "interior",
                    "default_thickness_m": self.GROSORES["muro_interior"],
                    "default_height_m": 3.0,
                    "default_material": "generic",
                    "description": "Muro interior exportado desde SpatialEngine"
                }
            ],
            "door_types": [
                {
                    "catalog_id": "DOOR_SINGLE_90CM",
                    "element_type": "door",
                    "door_type": "single",
                    "default_width_m": self.ANCHOS_PUERTA["puerta_simple"],
                    "default_height_m": 2.1,
                    "description": "Puerta simple exportada desde SpatialEngine"
                },
                {
                    "catalog_id": "DOOR_DOUBLE_180CM",
                    "element_type": "door",
                    "door_type": "double",
                    "default_width_m": self.ANCHOS_PUERTA["puerta_doble"],
                    "default_height_m": 2.1,
                    "description": "Puerta doble exportada desde SpatialEngine"
                },
                {
                    "catalog_id": "DOOR_EXIT_200CM",
                    "element_type": "door",
                    "door_type": "emergency_exit",
                    "default_width_m": self.ANCHOS_PUERTA["salida"],
                    "default_height_m": 2.1,
                    "description": "Salida exportada como puerta de emergencia"
                }
            ],
            "window_types": [],
            "column_types": [],
            "space_types": [
                {
                    "catalog_id": "SPACE_NAVIGABLE",
                    "space_type": "navigable_space",
                    "category": "room",
                    "default_function": "General",
                    "default_locomotion": ["walking", "rolling"],
                    "description": "Espacio navegable exportado desde hitos"
                },
                {
                    "catalog_id": "SPACE_DOOR_TRANSFER",
                    "space_type": "transfer_space",
                    "category": "door_space",
                    "default_function": "ConnectionSpace",
                    "default_locomotion": ["walking", "rolling"],
                    "description": "Espacio de transferencia asociado a puerta"
                },
                {
                    "catalog_id": "SPACE_EXIT",
                    "space_type": "exit_space",
                    "category": "exit",
                    "default_function": "ExitSpace",
                    "default_locomotion": ["walking", "rolling"],
                    "description": "Espacio de salida"
                },
                {
                    "catalog_id": "SPACE_VIRTUAL_BOUNDARY",
                    "space_type": "transfer_space",
                    "category": "virtual_boundary",
                    "default_function": "VirtualBoundary",
                    "default_locomotion": ["walking", "rolling"],
                    "description": "Frontera virtual topologica"
                }
            ],
            "beacon_types": [],
            "hazard_types": [],
            "stair_types": [],
            "ramp_types": [],
            "elevator_types": []
        }

    def _v2_physical_catalog_ref(self, tipo):
        if tipo == "muro_exterior":
            return "WALL_EXTERIOR_40CM"
        if tipo == "muro_interior":
            return "WALL_INTERIOR_15CM"
        if tipo == "puerta_doble":
            return "DOOR_DOUBLE_180CM"
        if self.is_exit_type(tipo):
            return "DOOR_EXIT_200CM"
        return "DOOR_SINGLE_90CM"

    def _v2_physical_elements(self):
        elementos = []
        element_id_map = {}
        authoring_elements = self.get_authoring_elements()

        for nombre, tipo, x1, y1, x2, y2 in authoring_elements:
            if self.is_virtual_boundary_type(tipo):
                # En v2 la frontera virtual es topologica; no se exporta como muro solido.
                continue

            if self.is_wall_type(tipo):
                element_type = "wall"
            elif self.is_door_type(tipo) or self.is_exit_type(tipo):
                element_type = "door"
            else:
                continue

            grosor = self.GROSORES.get(tipo)
            esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, grosor)
            if not esquinas:
                continue

            element_id = self._v2_normalizar_id("PE", nombre)
            attrs = {
                "original_type": tipo,
                "thickness_m": grosor,
                "is_virtual": False
            }
            if tipo in self.ANCHOS_PUERTA:
                attrs["width_m"] = self.ANCHOS_PUERTA[tipo]
            if self.is_exit_type(tipo):
                attrs["is_exit"] = True
                attrs["connector_type"] = "emergency_exit"

            elementos.append({
                "element_id": element_id,
                "level_id": "LEVEL_00",
                "element_type": element_type,
                "catalog_ref": self._v2_physical_catalog_ref(tipo),
                "centerline_2d": self._v2_linestring([(x1, y1), (x2, y2)]),
                "derived_footprint_2d": self._v2_polygon(esquinas),
                "label": nombre,
                "attributes": attrs
            })
            element_id_map[nombre] = element_id

        return elementos, element_id_map

    def _v2_spaces(self, element_id_map):
        spaces = []
        space_id_map = {}
        space_centroids = self.get_space_centroids()
        # self.hitos_bounds stores space footprints, not IndoorGML/MLSM boundaries.
        space_footprints = self.get_space_footprints()
        space_attributes = self.get_space_attributes()

        for nombre, coords in space_footprints:
            if nombre not in space_centroids or not coords:
                continue

            atributos_originales = space_attributes.get(nombre, {})
            space_type, category, function = self._v2_space_type_and_category(nombre, atributos_originales)
            cx, cy = space_centroids[nombre]
            locomotion_original = atributos_originales.get("locomotion", [])
            locomotion_v2 = self._v2_locomotion(locomotion_original)
            space_id = self._v2_normalizar_id("SPACE", nombre)

            attrs = dict(atributos_originales)
            attrs["locomotion_original"] = locomotion_original
            attrs["locomotion"] = locomotion_v2
            attrs["source"] = "spatialengine_hitos_bounds"

            space = {
                "space_id": space_id,
                "level_id": "LEVEL_00",
                "space_type": space_type,
                "name": nombre,
                "category": category,
                "function": function,
                "poi": False,
                "centroid_2d": self._v2_point(cx, cy),
                "footprint_2d": self._v2_polygon(coords),
                "attributes": attrs
            }

            if nombre in element_id_map:
                space["physical_element_ref"] = element_id_map[nombre]

            spaces.append(space)
            space_id_map[nombre] = space_id

        return spaces, space_id_map

    def _v2_space_polygon_by_name(self, nombre):
        # self.hitos_bounds stores space footprints, not MLSM boundaries.
        for space_name, coords in self.get_space_footprints():
            if space_name != nombre or not coords:
                continue
            try:
                poly = ShapelyPolygon(coords)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_empty or poly.area <= 0:
                    return None
                return poly
            except Exception:
                return None
        return None

    def _v2_line_segments_from_coords(self, coords):
        lines = []
        points = list(coords)
        for start, end in zip(points, points[1:]):
            line = ShapelyLineString([start, end])
            if not line.is_empty and line.length > 1e-9:
                lines.append(line)
        return lines

    def _v2_extract_lines_from_geometry(self, geom):
        if geom is None or geom.is_empty:
            return []

        geom_type = geom.geom_type
        if geom_type == "LineString":
            return [geom] if geom.length > 1e-9 else []
        if geom_type == "LinearRing":
            return self._v2_line_segments_from_coords(geom.coords)
        if geom_type == "MultiLineString":
            lines = []
            for part in geom.geoms:
                lines.extend(self._v2_extract_lines_from_geometry(part))
            return lines
        if geom_type == "Polygon":
            return self._v2_line_segments_from_coords(geom.exterior.coords)
        if geom_type == "MultiPolygon":
            lines = []
            for part in geom.geoms:
                lines.extend(self._v2_extract_lines_from_geometry(part))
            return lines
        if geom_type == "GeometryCollection":
            lines = []
            for part in geom.geoms:
                lines.extend(self._v2_extract_lines_from_geometry(part))
            return lines

        return []

    def _v2_longest_line(self, lines):
        useful_lines = [line for line in lines if line is not None and not line.is_empty and line.length > 1e-9]
        if not useful_lines:
            return None
        return max(useful_lines, key=lambda line: line.length)

    def _v2_boundary_centroid_fallback(self, origen, destino):
        space_centroids = self.get_space_centroids()
        return self._v2_linestring([space_centroids[origen], space_centroids[destino]]), True, "centroid_fallback"

    def _v2_boundary_geometry_between(self, origen, destino):
        poly_a = self._v2_space_polygon_by_name(origen)
        poly_b = self._v2_space_polygon_by_name(destino)

        if poly_a is None or poly_b is None:
            return self._v2_boundary_centroid_fallback(origen, destino)

        try:
            boundary_contact = poly_a.boundary.intersection(poly_b.boundary)
            line = self._v2_longest_line(self._v2_extract_lines_from_geometry(boundary_contact))
            if line is None:
                overlap = poly_a.intersection(poly_b)
                line = self._v2_longest_line(self._v2_extract_lines_from_geometry(overlap))
            if line is None:
                return self._v2_boundary_centroid_fallback(origen, destino)
            return self._v2_linestring(list(line.coords)), False, "geometry_contact"
        except Exception:
            return self._v2_boundary_centroid_fallback(origen, destino)

    def _v2_find_space_for_point(self, x, y, spaces):
        point = ShapelyPoint(x, y)
        fallback = spaces[0]["space_id"] if spaces else "UNKNOWN_SPACE"

        for space in spaces:
            coords = space.get("footprint_2d", {}).get("coordinates", [[]])[0]
            if len(coords) < 4:
                continue
            poly = ShapelyPolygon(coords)
            if poly.contains(point) or poly.touches(point):
                return space["space_id"], True

        return fallback, False

    def _v2_agent_spawns(self, spaces):
        spawns = []
        agent_positions = self.get_agent_spawns()

        for index, (x, y) in enumerate(agent_positions, start=1):
            space_ref, inferred = self._v2_find_space_for_point(x, y, spaces)
            spawns.append({
                "spawn_id": f"SPAWN_{index:03d}",
                "level_id": "LEVEL_00",
                "space_ref": space_ref,
                "position": self._v2_point(x, y),
                "capacity": 1,
                "allowed_profiles": ["walking", "rolling"],
                "attributes": {
                    "space_ref_inferred": inferred
                }
            })

        return spawns

    def _v2_boundary_type_for_connection(self, origen, destino):
        if self._v2_is_virtual_name(origen) or self._v2_is_virtual_name(destino):
            return "special_boundary"
        return "navigable_boundary"

    def _v2_boundaries_navegables(self, conexiones, space_id_map):
        boundaries = []
        boundary_id_map = {}

        for index, conn in enumerate(conexiones, start=1):
            if conn.get("tipo") != "navegable_puerta":
                continue

            origen = conn.get("origen")
            destino = conn.get("destino")
            if origen not in space_id_map or destino not in space_id_map:
                continue
            space_centroids = self.get_space_centroids()
            if origen not in space_centroids or destino not in space_centroids:
                continue

            boundary_id = f"BOUNDARY_NAV_{index:03d}"
            geometry_2d, approximate_geometry, derivation_source = self._v2_boundary_geometry_between(origen, destino)
            boundary = {
                "boundary_id": boundary_id,
                "level_id": "LEVEL_00",
                "boundary_type": self._v2_boundary_type_for_connection(origen, destino),
                "source_space_id": space_id_map[origen],
                "target_space_id": space_id_map[destino],
                "source_ref": {
                    "entity_type": "space",
                    "entity_id": space_id_map[origen]
                },
                "target_ref": {
                    "entity_type": "space",
                    "entity_id": space_id_map[destino]
                },
                "geometry_2d": geometry_2d,
                "attributes": {
                    "traversable": True,
                    "bidirectional": True,
                    "derived": True,
                    "approximate_geometry": approximate_geometry,
                    "derivation_source": derivation_source
                }
            }
            boundaries.append(boundary)
            boundary_id_map[(origen, destino)] = boundary_id
            boundary_id_map[(destino, origen)] = boundary_id

        return boundaries, boundary_id_map

    def _v2_distance_between(self, origen, destino):
        space_centroids = self.get_space_centroids()
        if origen not in space_centroids or destino not in space_centroids:
            return None
        x1, y1 = space_centroids[origen]
        x2, y2 = space_centroids[destino]
        return float(np.hypot(x2 - x1, y2 - y1))

    def _v2_connection_profiles(self, origen, destino):
        space_attributes = self.get_space_attributes()
        props_origen = space_attributes.get(origen, {})
        props_destino = space_attributes.get(destino, {})
        loc_origen = self._v2_locomotion(props_origen.get("locomotion", []))
        loc_destino = self._v2_locomotion(props_destino.get("locomotion", []))

        if loc_origen and loc_destino:
            comunes = [loc for loc in loc_origen if loc in loc_destino]
            return comunes or ["walking"]
        return loc_origen or loc_destino or ["walking"]

    def _v2_node_type_for_name(self, nombre):
        if self._v2_is_exit_name(nombre):
            return "exit_space"
        if self._v2_is_virtual_name(nombre):
            return "virtual_boundary"
        if "puerta" in str(nombre).lower():
            return "door_space"
        return "space"

    def _v2_connector_type_for_connection(self, origen, destino):
        if self._v2_is_exit_name(origen) or self._v2_is_exit_name(destino):
            return "emergency_exit"
        if self._v2_is_virtual_name(origen) or self._v2_is_virtual_name(destino):
            return "virtual_boundary"
        return "door_passage"

    def _v2_through_space_name(self, origen, destino):
        for nombre in (origen, destino):
            if self._v2_is_door_name(nombre) or self._v2_is_virtual_name(nombre):
                return nombre
        return None

    def _v2_add_graph_node(self, nodes, node_ids, graph_prefix, nombre, space_id_map):
        if nombre not in space_id_map:
            return None
        if nombre not in node_ids:
            node_id = self._v2_normalizar_id(graph_prefix, nombre)
            cx, cy = self.get_space_centroids().get(nombre, (0, 0))
            nodes.append({
                "node_id": node_id,
                "space_ref": space_id_map[nombre],
                "node_type": self._v2_node_type_for_name(nombre),
                "level_id": "LEVEL_00",
                "position": self._v2_point(cx, cy)
            })
            node_ids[nombre] = node_id
        return node_ids[nombre]

    def _v2_graphs(self, conexiones, spaces, physical_elements, boundaries, space_id_map, element_id_map, boundary_id_map):
        graph_defs = {
            "adyacencia_fisica": {
                "key": "adjacency_graph",
                "graph_id": "GRAPH_ADJ_LEVEL_00",
                "node_prefix": "N_ADJ",
                "edge_prefix": "E_ADJ",
                "purpose": "Contactos fisicos/topologicos derivados de conexiones adyacencia_fisica."
            },
            "navegable_puerta": {
                "key": "connectivity_graph",
                "graph_id": "GRAPH_CONN_LEVEL_00",
                "node_prefix": "N_CONN",
                "edge_prefix": "E_CONN",
                "purpose": "Conexiones atravesables derivadas de conexiones navegable_puerta."
            },
            "door_to_door": {
                "key": "door_to_door_graph",
                "graph_id": "GRAPH_D2D_LEVEL_00",
                "node_prefix": "N_D2D",
                "edge_prefix": "E_D2D",
                "purpose": "Grafo principal de evacuacion entre puertas, salidas y pasos."
            }
        }

        graphs = {}
        for conn_type, config in graph_defs.items():
            nodes = []
            node_ids = {}
            edges = []
            edge_index = 1
            space_centroids = self.get_space_centroids()

            for conn in conexiones:
                if conn.get("tipo") != conn_type:
                    continue

                origen = conn.get("origen")
                destino = conn.get("destino")
                if origen not in space_id_map or destino not in space_id_map:
                    continue
                if origen not in space_centroids or destino not in space_centroids:
                    continue

                source_node_id = self._v2_add_graph_node(nodes, node_ids, config["node_prefix"], origen, space_id_map)
                target_node_id = self._v2_add_graph_node(nodes, node_ids, config["node_prefix"], destino, space_id_map)
                if not source_node_id or not target_node_id:
                    continue

                edge = {
                    "edge_id": f"{config['edge_prefix']}_{edge_index:03d}",
                    "source_node_id": source_node_id,
                    "target_node_id": target_node_id,
                    "geometry_2d": self._v2_linestring([space_centroids[origen], space_centroids[destino]])
                }

                distance = self._v2_distance_between(origen, destino)
                if distance is not None:
                    edge["distance_m"] = distance

                if conn_type == "adyacencia_fisica":
                    edge["relationship_type"] = "physical_adjacency"
                    edge["traversable"] = False

                elif conn_type == "navegable_puerta":
                    through_name = self._v2_through_space_name(origen, destino)
                    edge["connector_type"] = self._v2_connector_type_for_connection(origen, destino)
                    edge["boundary_ref"] = boundary_id_map.get((origen, destino))
                    edge["allowed_flows"] = ["pedestrian"]
                    if edge["connector_type"] == "emergency_exit":
                        edge["allowed_flows"].append("emergency_exit")
                    edge["allowed_profiles"] = self._v2_connection_profiles(origen, destino)
                    edge["base_weight"] = distance if distance is not None else 1.0
                    edge["traversable"] = True
                    if through_name:
                        edge["through_space_id"] = space_id_map.get(through_name)
                        if through_name in element_id_map:
                            edge["through_element_id"] = element_id_map[through_name]
                        if self._v2_is_door_name(through_name):
                            width_key = "salida" if self._v2_is_exit_name(through_name) else "puerta_simple"
                            edge["width_m"] = self.ANCHOS_PUERTA.get(width_key)

                elif conn_type == "door_to_door":
                    contexto = conn.get("contexto")
                    edge["relationship_type"] = "door_to_door"
                    edge["through_space_id"] = space_id_map.get(contexto) if contexto in space_id_map else None
                    edge["traversable_by"] = self._v2_connection_profiles(origen, destino)
                    edge["base_weight"] = distance if distance is not None else 1.0
                    edge["capacity_persons"] = 1

                edge = {k: v for k, v in edge.items() if v is not None}
                edges.append(edge)
                edge_index += 1

            graphs[config["key"]] = {
                "graph_id": config["graph_id"],
                "graph_type": config["key"],
                "level_id": "LEVEL_00",
                "purpose": config["purpose"],
                "nodes": nodes,
                "edges": edges
            }

        graphs["vertical_connectivity_graph"] = {
            "graph_id": "GRAPH_VERTICAL_LEVEL_00",
            "graph_type": "vertical_connectivity_graph",
            "purpose": "Reservado para conexiones verticales; vacio en la primera exportacion v2.",
            "nodes": [],
            "edges": []
        }

        return graphs

    def _v2_write_json(self, datos, nombre_archivo):
        directorio_script = os.path.dirname(os.path.abspath(__file__))
        carpeta_destino = os.path.join(directorio_script, "escenarios")
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_completa = os.path.join(carpeta_destino, nombre_archivo)

        with open(ruta_completa, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)

        print(f"\n✅ PERFIL MLSM JSON v2 EXPORTADO A: '{ruta_completa}'")

    def exportar_mlsm_core_v2(self, conexiones, nombre_archivo="escenario_mlsm_v2.json"):
        """
        Exportacion paralela MLSM JSON v2.
        Traduce las estructuras actuales sin alterar el contrato v1 ni el dibujo.
        """
        physical_elements, element_id_map = self._v2_physical_elements()
        spaces, space_id_map = self._v2_spaces(element_id_map)
        boundaries, boundary_id_map = self._v2_boundaries_navegables(conexiones, space_id_map)
        graphs = self._v2_graphs(
            conexiones,
            spaces,
            physical_elements,
            boundaries,
            space_id_map,
            element_id_map,
            boundary_id_map
        )
        agent_spawns = self._v2_agent_spawns(spaces)

        ahora = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        datos = {
            "schema_version": "2.0.0",
            "metadata": {
                "name": self.nombre_archivo_base,
                "description": "Exportacion MLSM JSON v2 generada desde SpatialEngine.",
                "created_at": ahora,
                "modified_at": ahora,
                "author": "MLSM SpatialEngine",
                "reference_standard": "Perfil MLSM JSON v2 inspirado en IndoorGML/IndoorJSON"
            },
            "crs": {
                "type": "local",
                "srid": 0,
                "unit": "meters",
                "origin": {"x": 0, "y": 0, "z": 0},
                "description": "Sistema local 2D de SpatialEngine."
            },
            "levels": [
                {
                    "level_id": "LEVEL_00",
                    "name": "Planta baja",
                    "floor_index": 0,
                    "floor_z": 0.0,
                    "ceiling_z": 3.0,
                    "height_m": 3.0,
                    "description": "Planta unica exportada desde SpatialEngine.",
                    "spatial_extent_2d": self._v2_polygon([
                        (0, 0),
                        (self.ancho, 0),
                        (self.ancho, self.alto),
                        (0, self.alto)
                    ])
                }
            ],
            "catalogs": self._v2_catalogs(),
            "physical_elements": physical_elements,
            "spaces": spaces,
            "boundaries": boundaries,
            "graphs": graphs,
            "agent_spawns": agent_spawns,
            "agents": [],
            "beacons": [],
            "hazards": [],
            "simulation": {
                "time_step_s": 1.0,
                "max_steps": 600,
                "routing": {
                    "source_graph": "door_to_door_graph",
                    "use_dynamic_weights": False,
                    "use_beacon_risk": False,
                    "use_hazard_risk": False,
                    "use_congestion": False
                },
                "population": {
                    "mode": "from_agent_spawns",
                    "default_profile": "walking",
                    "default_count": len(agent_spawns)
                }
            },
            "indoorjson_mapping": {
                "core_mapping": {
                    "spaces": "CellSpace",
                    "boundaries": "CellBoundary",
                    "graphs.nodes": "Node",
                    "graphs.edges": "Edge"
                },
                "navigation_mapping": {
                    "navigable_space": "NavigableSpace",
                    "transfer_space": "TransferSpace",
                    "exit_space": "TransferSpace",
                    "special_boundary": "NavigableBoundary"
                },
                "mlsm_extensions": [
                    "physical_elements",
                    "catalogs",
                    "agent_spawns",
                    "simulation",
                    "door_to_door_graph"
                ],
                "compatibility": "Perfil propio MLSM inspirado en IndoorGML/IndoorJSON; no compatibilidad formal completa."
            }
        }

        self._v2_write_json(datos, nombre_archivo)

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
        nombre_final_v2 = nombre_final.replace(".json", "_v2.json")
        try:
            self.exportar_mlsm_core_v2(conexiones_detectadas, nombre_final_v2)
        except Exception as exc:
            print(f"\nWARNING: No se pudo exportar MLSM JSON v2: {exc}")

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
