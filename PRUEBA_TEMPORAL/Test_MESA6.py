import mesa
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import ListedColormap

# --- PARTE 1: CONFIGURACIÓN Y GEOMETRÍA ---
ANCHO, ALTO = 40, 25
RADIO_VISION_MUROS = 1.5 # Distancia a la que el agente "siente" la pared

# Los "Hitos" son las coordenadas (X, Y) de los nodos del Grafo Lógico.
# Representan el centro de habitaciones, puertas y cruces de pasillos.
HITOS = {
    'Sala_Reuniones': (8, 20), 'Puerta_Reuniones': (8, 15),
    'Oficina_Jefe': (8, 5), 'Puerta_Jefe': (12, 5),
    'Comedor': (20, 20), 'Puerta_Comedor': (20, 15),
    'Pasillo_Oeste': (12, 15), 'Pasillo_Centro': (20, 15),
    'Pasillo_Este': (32, 15), 'SALIDA': (38, 15)
}

# --- PARTE 2: EL CEREBRO (MODELO) ---
class ModeloHibrido(mesa.Model):
    def __init__(self):
        super().__init__()
        # Decisión 1: Espacio Continuo. Los agentes tienen coordenadas float (10.5, 20.1)
        # torus=False significa que el mundo no es redondo (si sales por la dcha, no apareces por la izq)
        self.space = mesa.space.ContinuousSpace(ANCHO, ALTO, torus=False)
        
        # Decisión 2: Matriz Numpy para la Física (Muros)
        self.mapa_muros = np.zeros((ANCHO, ALTO)) 
        self.construir_paredes() # Llenamos la matriz con 1s donde hay muro
        
        # Decisión 3: NetworkX para la Lógica (Navegación)
        self.grafo_logico = nx.Graph()
        self.construir_grafo()
        
        self.fuegos = []

        # Crear Agentes en posiciones específicas
        posiciones = [(5, 22), (10, 22), (5, 5), (10, 5), (18, 22), (22, 22)]
        for i, pos in enumerate(posiciones):
            a = AgenteInteligente(i, self)
            self.agents.add(a)
            self.space.place_agent(a, pos)

    def tiene_linea_vision(self, p1, p2):
        """
        ALGORITMO DE RAYCASTING (Traza de Rayo)
        Comprueba píxel a píxel si hay un muro entre el punto p1 y p2.
        Se usa para ver si el agente puede coger un atajo.
        """
        dist = np.linalg.norm(p2 - p1)
        pasos = int(dist * 2) # Muestreamos 2 veces por metro para precisión
        if pasos == 0: return True
        
        # Interpolación Lineal: Recorremos la línea imaginaria
        for i in range(pasos + 1):
            t = i / pasos
            x = int(p1[0] + (p2[0] - p1[0]) * t)
            y = int(p1[1] + (p2[1] - p1[1]) * t)
            
            # Si nos salimos del mapa o tocamos un 1 (Muro), no hay visión
            if not (0 <= x < ANCHO and 0 <= y < ALTO): return False
            if self.mapa_muros[x, y] == 1: return False
        return True

    def construir_paredes(self):
        # Aquí "pintamos" los muros en la matriz poniendo 1s.
        self.mapa_muros[0,:] = 1; self.mapa_muros[-1,:] = 1 # Bordes sup/inf
        self.mapa_muros[:,0] = 1; self.mapa_muros[:,-1] = 1 # Bordes izq/der
        
        # Muros interiores (Coordenadas manuales para definir habitaciones)
        self.mapa_muros[0:15, 15] = 1  
        self.mapa_muros[15, 15:25] = 1 
        self.mapa_muros[15:30, 15] = 1 
        self.mapa_muros[0:15, 8] = 1   
        
        # Huecos (Puertas): Ponemos 0s para abrir paso
        self.mapa_muros[7:10, 15] = 0 
        self.mapa_muros[19:22, 15] = 0
        self.mapa_muros[ANCHO-2:ANCHO, 13:17] = 0 # Salida

    def construir_grafo(self):
        # Conectamos los HITOS lógicamente. Esto crea las líneas del grafo.
        conexiones = [
            ('Sala_Reuniones', 'Puerta_Reuniones'), ('Puerta_Reuniones', 'Pasillo_Oeste'),
            ('Oficina_Jefe', 'Puerta_Jefe'), ('Puerta_Jefe', 'Pasillo_Oeste'),
            ('Comedor', 'Puerta_Comedor'), ('Puerta_Comedor', 'Pasillo_Centro'),
            ('Pasillo_Oeste', 'Pasillo_Centro'), ('Pasillo_Centro', 'Pasillo_Este'), 
            ('Pasillo_Este', 'SALIDA')
        ]
        for u, v in conexiones:
            p1, p2 = np.array(HITOS[u]), np.array(HITOS[v])
            distancia = np.linalg.norm(p1 - p2)
            self.grafo_logico.add_edge(u, v, weight=distancia)
    
    def es_transitable(self, pos):
        # Verifica colisión contra muro
        x, y = int(pos[0]), int(pos[1])
        if 0 <= x < ANCHO and 0 <= y < ALTO:
            return self.mapa_muros[x, y] == 0
        return False
    
    def crear_fuego(self, x, y):
        # Evento dinámico: Añadimos fuego y actualizamos pesos del grafo
        self.fuegos.append({'pos': np.array([x, y]), 'radio': 3.0})
        for u, v in self.grafo_logico.edges():
            p1, p2 = np.array(HITOS[u]), np.array(HITOS[v])
            peso = np.linalg.norm(p1 - p2)
            for f in self.fuegos:
                mid = (p1 + p2) / 2 # Punto medio de la arista
                if np.linalg.norm(mid - f['pos']) < 5.0: peso += 1000 # Penalización
            self.grafo_logico[u][v]['weight'] = peso
    
    def step(self): self.agents.shuffle_do("step")

# --- PARTE 3: EL AGENTE (FÍSICA + LÓGICA) ---
class AgenteInteligente(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.velocidad = 0.6
        self.destino_actual = None
        self.plan_maestro = [] # Lista de coordenadas (Ruta Global)
        
        # Para visualización del rastro
        self.traza_x = []
        self.traza_y = []

    def step(self):
        # Guardar historial para pintar la línea amarilla
        if self.pos is not None:
            self.traza_x.append(self.pos[0])
            self.traza_y.append(self.pos[1])
            
        # 1. PLANIFICACIÓN GLOBAL (Si no tengo ruta, busco una)
        if not self.plan_maestro:
            self.calcular_ruta_dijkstra()
        
        # 2. OPTIMIZACIÓN LOCAL (String Pulling / Atajos)
        # Si mi plan es A -> B -> C, y veo C directamente, me salto B.
        if len(self.plan_maestro) >= 2:
            siguiente = self.plan_maestro[0]
            subsiguiente = self.plan_maestro[1]
            if self.model.tiene_linea_vision(np.array(self.pos), subsiguiente):
                self.plan_maestro.pop(0) # Borrar 'siguiente'
                self.destino_actual = self.plan_maestro[0]

        # 3. EJECUCIÓN (Movimiento)
        if self.destino_actual is not None:
            self.mover_con_fisica()

    def calcular_ruta_dijkstra(self):
        pos = np.array(self.pos)
        # Buscar cuál es el Hito más cercano a mí (Euclídeo)
        nodo_cercano = min(HITOS, key=lambda k: np.linalg.norm(pos - np.array(HITOS[k])))
        try:
            # Algoritmo A* o Dijkstra de NetworkX
            ruta = nx.shortest_path(self.model.grafo_logico, nodo_cercano, 'SALIDA', weight='weight')
            self.plan_maestro = [np.array(HITOS[n]) for n in ruta]
            if self.plan_maestro: self.destino_actual = self.plan_maestro[0]
        except: pass

    def mover_con_fisica(self):
        pos = np.array(self.pos)
        vec_objetivo = self.destino_actual - pos
        dist = np.linalg.norm(vec_objetivo)
        
        # ¿Llegué al objetivo?
        if dist < 0.5: 
            if self.plan_maestro:
                self.plan_maestro.pop(0)
                self.destino_actual = self.plan_maestro[0] if self.plan_maestro else None
            return

        # FÍSICA DE REPULSIÓN (Evitar rozar paredes)
        fuerza_pared = np.zeros(2)
        xi, yi = int(pos[0]), int(pos[1])
        rango = 1 # Mirar celdas vecinas
        for dx in range(-rango, rango+1):
            for dy in range(-rango, rango+1):
                nx, ny = xi+dx, yi+dy
                # Si hay muro cerca
                if 0 <= nx < ANCHO and 0 <= ny < ALTO and self.model.mapa_muros[nx, ny] == 1:
                    # Crear vector que empuja en dirección contraria a la pared
                    vec_alejamiento = pos - np.array([nx+0.5, ny+0.5]) # +0.5 es el centro del muro
                    dist_muro = np.linalg.norm(vec_alejamiento)
                    if dist_muro < RADIO_VISION_MUROS:
                         fuerza_pared += (vec_alejamiento / dist_muro) * (1.2 / dist_muro)

        # Sumar Vectores: Atracción Meta + Repulsión Pared
        direccion = (vec_objetivo/dist) + fuerza_pared
        
        # Normalizar (para no correr más de la cuenta)
        norm = np.linalg.norm(direccion)
        movimiento = (direccion/norm) * self.velocidad if norm > 0 else np.zeros(2)
        
        nueva_pos = pos + movimiento
        
        # Check Final: ¿Choco con muro?
        if self.model.es_transitable(nueva_pos):
            self.model.space.move_agent(self, tuple(nueva_pos))

# --- PARTE 4: VISUALIZACIÓN "GRID & NEON" ---
model = ModeloHibrido()
fig, ax = plt.subplots(figsize=(10, 7), facecolor='#101010')
ax.set_facecolor('#101010')

# Pre-cálculo de líneas del Grid para dibujar rápido
lineas_x, lineas_y = [], []
for x in range(ANCHO): lineas_x.extend([x, x, None]); lineas_y.extend([0, ALTO, None])
for y in range(ALTO): lineas_x.extend([0, ANCHO, None]); lineas_y.extend([y, y, None])

cid = fig.canvas.mpl_connect('button_press_event', lambda e: model.crear_fuego(e.xdata, e.ydata) if e.xdata else None)

def update(frame):
    model.step()
    ax.clear()

    # 1. EL NAVMESH (La Cuadrícula Visible)
    # Dibujamos líneas verdes tenues. Esto representa el NavMesh transitable.
    ax.plot(lineas_x, lineas_y, c='#004400', linewidth=0.5, alpha=0.3, zorder=0)
    
    # 2. LOS MUROS (Capa Física)
    # Tapamos la cuadrícula con negro donde hay muro.
    ax.imshow(model.mapa_muros.T, cmap=plt.cm.gray, origin='lower', alpha=0.9, extent=[0, ANCHO, 0, ALTO], zorder=1)

    # 3. EL GRAFO (Capa Lógica - Neon)
    # Nodos
    for nombre, pos in HITOS.items():
        ax.scatter(*pos, c='#FF00FF', s=80, edgecolors='white', zorder=10) # Magenta
        # Nombre nodo
        if 'SALIDA' in nombre: ax.text(pos[0], pos[1]+1, "SALIDA", color='lime', ha='center', fontsize=8, zorder=10)
    
    # Aristas
    for u, v in model.grafo_logico.edges():
        p1, p2 = HITOS[u], HITOS[v]
        peso = model.grafo_logico[u][v]['weight']
        col = 'red' if peso > 500 else '#00FFFF' # Cian / Rojo
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], c=col, linewidth=1.5, zorder=9)

    # 4. AGENTES (Capa Dinámica)
    if len(model.agents) > 0:
        for a in model.agents:
            # Traza Real (Amarillo)
            ax.plot(a.traza_x, a.traza_y, c='yellow', linewidth=1, alpha=0.6)
            # Intención (Punteada blanca - Muestra atajos)
            if a.destino_actual is not None:
                ax.plot([a.pos[0], a.destino_actual[0]], [a.pos[1], a.destino_actual[1]], 
                        c='white', linestyle=':', linewidth=0.8, alpha=0.8)
        
        xs = [a.pos[0] for a in model.agents]
        ys = [a.pos[1] for a in model.agents]
        ax.scatter(xs, ys, c='orange', s=50, edgecolors='black', zorder=11)

    # 5. FUEGOS
    for f in model.fuegos:
        ax.add_patch(plt.Circle(tuple(f['pos']), f['radio'], color='red', alpha=0.6, zorder=5))

    ax.set_title(f"NavMesh Grid & Atajos | Frame {frame}", color='white')
    ax.axis('off')

ani = animation.FuncAnimation(fig, update, frames=300, interval=40)
plt.show()