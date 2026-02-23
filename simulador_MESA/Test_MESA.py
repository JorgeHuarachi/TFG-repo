import mesa
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle

# --- CONFIGURACIÓN ---
ANCHO = 50
ALTO = 50
PIXELS_POR_NODO = 2  # Densidad del grafo de navegación (menor = más precisión, más lento)

# --- 1. CLASE AGENTE CON FÍSICA (CORREGIDA) ---
class AgenteContinuo(mesa.Agent):
    def __init__(self, unique_id, model, salida_coords):
        super().__init__(model)
        self.unique_id = unique_id
        self.salida_final = np.array(salida_coords)
        self.velocidad = 0.8
        self.ruta_nodos = []
        self.target_actual = None
        
        # CORRECCIÓN: Inicializamos vacíos para evitar el error de 'NoneType'
        self.traza_x = [] 
        self.traza_y = [] 

    def step(self):
        # Guardamos la posición actual si el agente está en el mapa
        if self.pos is not None:
            self.traza_x.append(self.pos[0])
            self.traza_y.append(self.pos[1])
        
        # 1. PERCEPCIÓN
        pos_arr = np.array(self.pos)
        dist_salida = np.linalg.norm(pos_arr - self.salida_final)
        
        # Si llegué a la salida, desaparezco
        if dist_salida < 1.0:
            self.model.agentes_salvados += 1
            self.remove()
            return

        # Si no tengo ruta o estoy cerca del waypoint, recalculo
        if self.target_actual is None or np.linalg.norm(pos_arr - self.target_actual) < 1.5:
            self.ruta_nodos = self.model.obtener_ruta_segura(self.pos, tuple(self.salida_final))
            if len(self.ruta_nodos) > 1:
                # Tomamos un punto más adelante para suavizar (Lookahead)
                idx = min(2, len(self.ruta_nodos)-1) 
                self.target_actual = np.array(self.ruta_nodos[idx])
            else:
                self.target_actual = self.salida_final

        # 2. MOVIMIENTO (Física)
        self.mover_con_fisica()

    def mover_con_fisica(self):
        if self.pos is None: return # Seguridad extra
        
        pos_actual = np.array(self.pos)
        
        # Fuerza Atracción
        vector_destino = self.target_actual - pos_actual
        dist = np.linalg.norm(vector_destino)
        direccion = vector_destino / dist if dist > 0 else np.zeros(2)

        # Fuerza Repulsión (Muros y Agentes)
        fuerza_repulsion = np.zeros(2)
        
        # Repulsión Agentes
        vecinos = self.model.space.get_neighbors(self.pos, 1.5, include_center=False)
        for v in vecinos:
            diff = pos_actual - np.array(v.pos)
            d = np.linalg.norm(diff)
            if d > 0: force = (diff / d) * (0.3 / d); fuerza_repulsion += force

        # Vector Resultante
        vector_final = direccion + fuerza_repulsion
        norm = np.linalg.norm(vector_final)
        movimiento = (vector_final / norm) * self.velocidad if norm > 0 else np.zeros(2)
        
        nueva_pos = pos_actual + movimiento
        
        # Chequeo simple de muros (Rebotar si intento cruzar pared)
        if not self.model.es_transitable(nueva_pos):
            return 

        self.model.space.move_agent(self, tuple(nueva_pos))

class ModeloOficina(mesa.Model):
    def __init__(self):
        super().__init__()
        self.width = ANCHO
        self.height = ALTO
        self.space = mesa.space.ContinuousSpace(ANCHO, ALTO, torus=False)
        self.agentes_salvados = 0
        
        # 1. GENERAR MAPA (1 = Muro, 0 = Libre)
        self.mapa_muros = np.zeros((ANCHO, ALTO))
        self.generar_habitaciones()
        
        # 2. GENERAR GRAFO DE NAVEGACIÓN
        # Creamos un grafo menos denso para no saturar la CPU
        self.scale = PIXELS_POR_NODO
        self.w_g = int(ANCHO/self.scale)
        self.h_g = int(ALTO/self.scale)
        self.grafo = nx.grid_2d_graph(self.w_g, self.h_g)
        
        # Eliminar nodos que caen en muros
        nodos_muros = []
        for node in self.grafo.nodes():
            rx, ry = node[0]*self.scale, node[1]*self.scale
            if self.mapa_muros[int(rx), int(ry)] == 1:
                nodos_muros.append(node)
        self.grafo.remove_nodes_from(nodos_muros)
        
        # 3. GESTIÓN DE PELIGROS
        self.fuegos = [] # Lista de focos de fuego [(x, y, radio)]

        # 4. CREAR AGENTES
        self.salida = (ANCHO-2, ALTO/2)
        # CORRECCIÓN:
        for i in range(15): # <--- Cambiamos '_' por 'i'
            intentos = 0
            while intentos < 100:
                x, y = np.random.randint(1, ANCHO-1), np.random.randint(1, ALTO-1)
                if self.mapa_muros[x, y] == 0: 
                    # Usamos 'i' como ID único
                    a = AgenteContinuo(i, self, self.salida) 
                    self.agents.add(a)
                    self.space.place_agent(a, (x, y))
                    break
                intentos += 1

    def generar_habitaciones(self):
        # Paredes exteriores
        self.mapa_muros[0,:] = 1; self.mapa_muros[-1,:] = 1
        self.mapa_muros[:,0] = 1; self.mapa_muros[:,-1] = 1
        
        # Pasillo central horizontal
        # Habitaciones arriba y abajo
        y_pasillo_min, y_pasillo_max = 22, 28
        
        # Paredes verticales interiores (divisiones de cuartos)
        x_cuts = [15, 30]
        for x in x_cuts:
            self.mapa_muros[x, 0:y_pasillo_min] = 1 # Muro arriba
            self.mapa_muros[x, y_pasillo_max:ALTO] = 1 # Muro abajo
            
        # Paredes horizontales del pasillo
        self.mapa_muros[:, y_pasillo_min] = 1
        self.mapa_muros[:, y_pasillo_max] = 1
        
        # Puertas (huecos en los muros)
        puertas = [(7, y_pasillo_min), (22, y_pasillo_min), (40, y_pasillo_min),
                   (7, y_pasillo_max), (22, y_pasillo_max), (40, y_pasillo_max),
                   (15, 10), (30, 40)] # Puertas inter-habitacion
        
        for px, py in puertas:
            self.mapa_muros[px-2:px+2, py] = 0 # Abrir hueco
            self.mapa_muros[px, py-2:py+2] = 0 
            
        # Limpiar salida
        self.mapa_muros[ANCHO-5:ANCHO, int(ALTO/2)-4:int(ALTO/2)+4] = 0

    def es_transitable(self, pos):
        # Verifica si una coordenada cae en un muro
        x, y = int(pos[0]), int(pos[1])
        if 0 <= x < ANCHO and 0 <= y < ALTO:
            return self.mapa_muros[x, y] == 0
        return False

    def crear_fuego_en(self, x, y):
        # Añade un nuevo foco de incendio
        self.fuegos.append({'pos': np.array([x, y]), 'radio': 1.0})
        print(f"🔥 FUEGO INICIADO EN ({x:.1f}, {y:.1f})")

    def step(self):
        # Expandir fuegos (LENTO)
        for fuego in self.fuegos:
            fuego['radio'] += 0.05 # Expansión lenta
            
        # Recalcular pesos del grafo basado en fuegos
        self.actualizar_pesos_grafo()
        self.agents.shuffle_do("step")

    def actualizar_pesos_grafo(self):
        # Optimización: Solo actualizar nodos cerca de los fuegos si hay muchos
        if not self.fuegos: return

        for u, v in self.grafo.edges():
            peso = 1
            # Coordenadas reales del nodo destino v
            vx, vy = v[0]*self.scale, v[1]*self.scale
            
            for fuego in self.fuegos:
                dist = np.linalg.norm([vx - fuego['pos'][0], vy - fuego['pos'][1]])
                if dist < fuego['radio']:
                    peso = 10000 # Fuego activo
                    break # Suficiente para marcarlo como mortal
                elif dist < fuego['radio'] + 8: # Radio de humo/calor
                    peso += 50 # Zona peligrosa, evitar si es posible
            
            self.grafo[u][v]['weight'] = peso

    def obtener_ruta_segura(self, origen, destino):
        # Convertir float -> nodo grid
        n_origen = (int(origen[0]/self.scale), int(origen[1]/self.scale))
        n_destino = (int(destino[0]/self.scale), int(destino[1]/self.scale))
        
        # Clamp (asegurar que está dentro de límites)
        w, h = self.w_g -1, self.h_g -1
        n_origen = (min(max(n_origen[0],0), w), min(max(n_origen[1],0), h))
        
        try:
            path = nx.shortest_path(self.grafo, n_origen, n_destino, weight='weight')
            return [(p[0]*self.scale, p[1]*self.scale) for p in path]
        except:
            return [origen]

# --- VISUALIZACIÓN E INTERACCIÓN CON VISIÓN DE GRAFO ---
model = ModeloOficina()
fig, ax = plt.subplots(figsize=(9,9))

# Pre-calculamos las líneas del grafo para no matar la CPU dibujándolas cada frame
# Esto extrae todas las aristas de NetworkX y las escala al mundo real
lineas_grafo_x = []
lineas_grafo_y = []
for u, v in model.grafo.edges():
    ux, uy = u[0]*model.scale, u[1]*model.scale
    vx, vy = v[0]*model.scale, v[1]*model.scale
    # Añadimos par de puntos y un None para que matplotlib no una todas las lineas
    lineas_grafo_x.extend([ux, vx, None]) 
    lineas_grafo_y.extend([uy, vy, None])

def on_click(event):
    if event.xdata is not None and event.ydata is not None:
        model.crear_fuego_en(event.xdata, event.ydata)

cid = fig.canvas.mpl_connect('button_press_event', on_click)

def update(frame):
    model.step()
    ax.clear()
    
    # 1. Dibujar Muros (Fondo)
    ax.imshow(model.mapa_muros.T, cmap='Greys', origin='lower', extent=[0, ANCHO, 0, ALTO], alpha=0.2)
    
    # 2. DIBUJAR EL GRAFO DE NETWORKX (NUEVO)
    # Dibujamos la "malla" invisible que usan para pensar
    ax.plot(lineas_grafo_x, lineas_grafo_y, c='gray', alpha=0.15, linewidth=0.5, zorder=1)
    # Dibujamos los nodos (puntitos)
    # nodos_x = [n[0]*model.scale for n in model.grafo.nodes()]
    # nodos_y = [n[1]*model.scale for n in model.grafo.nodes()]
    # ax.scatter(nodos_x, nodos_y, s=1, c='gray', alpha=0.2)

    # 3. Dibujar Fuegos
    for fuego in model.fuegos:
        c1 = plt.Circle(tuple(fuego['pos']), fuego['radio'], color='red', alpha=0.6, zorder=2)
        c2 = plt.Circle(tuple(fuego['pos']), fuego['radio']+8, color='orange', alpha=0.2, zorder=2)
        ax.add_patch(c2)
        ax.add_patch(c1)

    # 4. Dibujar Agentes
    if len(model.agents) > 0:
        # A. RASTRO FÍSICO (Azul - Lo que realmente recorren)
        for agente in model.agents:
            ax.plot(agente.traza_x, agente.traza_y, '-', color='blue', alpha=0.3, linewidth=0.5)
        
        # B. RUTA LÓGICA DEL AGENTE 0 (Amarillo - Lo que NetworkX dice)
        # Seleccionamos al primer agente vivo para ver su cerebro
        agentes_vivos = list(model.agents)
        if len(agentes_vivos) > 0:
            agente_vip = agentes_vivos[0]
            if agente_vip.ruta_nodos:
                # Extraer coordenadas de la ruta planificada
                rx = [p[0] for p in agente_vip.ruta_nodos]
                ry = [p[1] for p in agente_vip.ruta_nodos]
                # Dibujar la línea de NetworkX
                ax.plot(rx, ry, color='gold', linewidth=2, linestyle='--', label='Plan NetworkX (Agente 0)', zorder=4)
                # Marcar el siguiente Waypoint objetivo
                if agente_vip.target_actual is not None:
                     ax.scatter([agente_vip.target_actual[0]], [agente_vip.target_actual[1]], c='gold', marker='x', s=100, zorder=4)

        # C. Posiciones actuales
        xs = [a.pos[0] for a in model.agents]
        ys = [a.pos[1] for a in model.agents]
        ax.scatter(xs, ys, c='blue', edgecolors='white', s=50, zorder=5)

    # 5. Salida
    ax.scatter([model.salida[0]], [model.salida[1]], c='green', s=200, marker='*', zorder=6)

    ax.set_xlim(0, ANCHO)
    ax.set_ylim(0, ALTO)
    ax.set_title(f"Gris: Grafo NetworkX | Amarillo: Plan Algoritmo | Azul: Movimiento Real\nPasos: {frame}")
    ax.legend(loc='upper left', fontsize='small')

print("Iniciando Modo Debug Visual...")
ani = animation.FuncAnimation(fig, update, frames=300, interval=50)
plt.show()