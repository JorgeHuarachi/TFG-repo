import mesa
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle

# --- 1. CONFIGURACIÓN FÍSICA ---
ANCHO, ALTO = 40, 25

# --- AJUSTES DE CONFIGURACIÓN PARA SUAVIDAD ---
RADIO_FISICO = 0.4        
RADIO_PERSONAL = 0.8      
RADIO_VISION_MUROS = 0.8  # Reducido de 1.5 a 0.8 (Menos paranoico con las paredes)
FUERZA_PARED = 1.2        # Reducida la fuerza de rebote
RUIDO_BASE = 0.05         # Ruido casi imperceptible
FUERZA_MAXIMA = 3.0
VELOCIDAD_BASE = 0.1
RADIO_ZONA_SALIDA = 2.0   

HITOS = {
    'SALIDA': (39, 20.5), 'Habitacion_1': (9, 20.5), 'Habitacion_2': (4, 8.5),
    'Habitacion_3': (15, 3), 'Habitacion_4': (25.5, 3), 'Habitacion_5': (34, 8.5),
    'Habitacion_6': (28.5, 20.5), 'Habitacion_7': (18.5, 11.5), 'Puerta_1': (3.5, 17),
    'Puerta_2': (8, 14.5), 'Puerta_3': (8, 10.5), 'Puerta_4': (8, 3.5),
    'Puerta_5': (13.5, 6), 'Puerta_6': (22, 2.5), 'Puerta_7': (25.5, 6),
    'Puerta_8': (29, 3), 'Puerta_9': (29, 11.5), 'Puerta_10': (22.5, 17),
    'Puerta_11': (18, 20.5), 'Puerta_12': (11.5, 17), 'Puerta_13': (26.5, 17),
    'Puerta_14': (34.5, 17), 'Puerta_15': (39, 10),
}

# --- 2. MODELO ---
class ModeloIntencion(mesa.Model):
    def __init__(self):
        super().__init__()
        self.space = mesa.space.ContinuousSpace(ANCHO, ALTO, torus=False)
        self.mapa_muros = np.zeros((ANCHO, ALTO))
        self.construir_paredes()
        self.grafo_logico = nx.Graph()
        self.construir_grafo()
        self.fuegos = []
        self.evacuados = 0
        
        # LISTA MAESTRA (Para mantener referencias visuales)
        self.todos_los_agentes = []

        posiciones = [(2, 21), (4, 20), (9, 21), (13, 19), (14, 20), (5, 15), (3, 13), 
                      (5, 12), (2, 6), (4, 4), (2, 8), (11, 4), (12, 3), (16, 4), 
                      (20, 2), (20, 3), (26, 4), (25, 2), (23, 15), (25, 10), 
                      (33, 6), (33, 16), (25, 21), (15, 11)]
        
        for i, pos in enumerate(posiciones):
            a = AgentePro(i, self)
            self.agents.add(a)
            self.space.place_agent(a, pos)
            self.todos_los_agentes.append(a) 

    def tiene_linea_vision(self, p1, p2):
        dist = np.linalg.norm(p2 - p1)
        pasos = int(dist * 2)
        if pasos == 0: return True
        for i in range(pasos + 1):
            t = i / pasos
            x = int(p1[0] + (p2[0] - p1[0]) * t)
            y = int(p1[1] + (p2[1] - p1[1]) * t)
            if not (0 <= x < ANCHO and 0 <= y < ALTO): return False
            if self.mapa_muros[x, y] == 1: return False
        return True

    def construir_paredes(self):
        self.mapa_muros[:,:] = 0
        self.mapa_muros[0,:] = 1; self.mapa_muros[-1,:] = 1
        self.mapa_muros[:,0] = 1; self.mapa_muros[:,-1] = 1
        self.mapa_muros[0:40, 0] = 1; self.mapa_muros[39, 0:25] = 1
        self.mapa_muros[0:40, 24] = 1; self.mapa_muros[0, 0:25] = 1
        self.mapa_muros[0:40, 17] = 1; self.mapa_muros[8, 0:18] = 1
        self.mapa_muros[29, 0:18] = 1; self.mapa_muros[8:30, 6] = 1
        self.mapa_muros[22, 0:7] = 1; self.mapa_muros[18, 17:25] = 1
        self.mapa_muros[3:5, 17] = 0; self.mapa_muros[18, 20:22] = 0
        self.mapa_muros[11:13, 17] = 0; self.mapa_muros[29, 11:13] = 0
        self.mapa_muros[22:24, 17] = 0; self.mapa_muros[34:36, 17] = 0
        self.mapa_muros[13:15, 6] = 0; self.mapa_muros[22, 2:4] = 0
        self.mapa_muros[8, 10:12] = 0; self.mapa_muros[8, 3:5] = 0
        self.mapa_muros[25:27, 6] = 0; self.mapa_muros[29, 2:5] = 0
        self.mapa_muros[39, 20:22] = 0; self.mapa_muros[39, 9:12] = 0
        self.mapa_muros[8, 14:16] = 0; self.mapa_muros[26:28, 17] = 0

    def construir_grafo(self):
        conexiones = [
            ('SALIDA', 'Habitacion_6'), ('Habitacion_1', 'Puerta_1'), ('Habitacion_1', 'Puerta_11'),
            ('Habitacion_1', 'Puerta_12'), ('Habitacion_2', 'Puerta_1'), ('Habitacion_2', 'Puerta_2'),
            ('Habitacion_2', 'Puerta_3'), ('Habitacion_2', 'Puerta_4'), ('Habitacion_3', 'Puerta_4'),
            ('Habitacion_3', 'Puerta_5'), ('Habitacion_3', 'Puerta_6'), ('Habitacion_4', 'Puerta_6'),
            ('Habitacion_4', 'Puerta_7'), ('Habitacion_4', 'Puerta_8'), ('Habitacion_5', 'Puerta_8'),
            ('Habitacion_5', 'Puerta_9'), ('Habitacion_5', 'Puerta_14'), ('Habitacion_5', 'Puerta_15'),
            ('Habitacion_6', 'Puerta_10'), ('Habitacion_6', 'Puerta_11'), ('Habitacion_6', 'Puerta_13'),
            ('Habitacion_6', 'Puerta_14'), ('Habitacion_7', 'Puerta_2'), ('Habitacion_7', 'Puerta_3'),
            ('Habitacion_7', 'Puerta_5'), ('Habitacion_7', 'Puerta_7'), ('Habitacion_7', 'Puerta_9'),
            ('Habitacion_7', 'Puerta_10'), ('Habitacion_7', 'Puerta_12'), ('Habitacion_7', 'Puerta_13'),
        ]
        for u, v in conexiones:
            p1, p2 = np.array(HITOS[u]), np.array(HITOS[v])
            self.grafo_logico.add_edge(u, v, weight=np.linalg.norm(p1 - p2))
    
    def es_transitable(self, pos):
        x, y = int(pos[0]), int(pos[1])
        if 0 <= x < ANCHO and 0 <= y < ALTO: return self.mapa_muros[x, y] == 0
        return False
    
    def crear_fuego(self, x, y):
        self.fuegos.append({'pos': np.array([x, y]), 'radio': 2.0})
        for u, v in self.grafo_logico.edges():
            p1, p2 = np.array(HITOS[u]), np.array(HITOS[v])
            peso = np.linalg.norm(p1 - p2)
            for f in self.fuegos:
                mid = (p1 + p2) / 2
                if np.linalg.norm(mid - f['pos']) < 6.0: peso += 5000
            self.grafo_logico[u][v]['weight'] = peso
        for agente in self.agents: agente.necesita_recalcular = True

    def step(self): self.agents.shuffle_do("step")

# --- 3. AGENTE (Física Suave + Intención) ---
class AgentePro(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.velocidad_actual = np.zeros(2)
        self.destino_actual = None
        self.plan_maestro = []
        self.necesita_recalcular = False
        self.traza_x = []
        self.traza_y = []
        self.evacuado = False

    def step(self):
        if self.evacuado: return 
        
        self.traza_x.append(self.pos[0])
        self.traza_y.append(self.pos[1])
        
        if self.necesita_recalcular:
            self.plan_maestro = []; self.destino_actual = None; self.necesita_recalcular = False
        
        if not self.plan_maestro: self.calcular_ruta_dijkstra()
        
        # LÓGICA DE ATAJOS (Visión): Esto está bien, lo dejamos.
        if len(self.plan_maestro) >= 2:
            if self.model.tiene_linea_vision(np.array(self.pos), self.plan_maestro[1]):
                self.plan_maestro.pop(0)
                self.destino_actual = self.plan_maestro[0]

        if self.destino_actual is not None: 
            self.mover_suave_v2()
            self.verificar_salida()

    def verificar_salida(self):
        dist_salida = np.linalg.norm(np.array(self.pos) - np.array(HITOS['SALIDA']))
        if dist_salida < RADIO_ZONA_SALIDA:
            self.model.evacuados += 1
            self.evacuado = True 
            self.model.space.remove_agent(self)
            self.remove() 

    def calcular_ruta_dijkstra(self):
        pos = np.array(self.pos)
        nodo_cercano = min(HITOS, key=lambda k: np.linalg.norm(pos - np.array(HITOS[k])))
        try:
            ruta = nx.shortest_path(self.model.grafo_logico, nodo_cercano, 'SALIDA', weight='weight')
            self.plan_maestro = [np.array(HITOS[n]) for n in ruta]
            if self.plan_maestro: self.destino_actual = self.plan_maestro[0]
        except: pass

    def mover_suave_v2(self):
        pos = np.array(self.pos)
        vec_objetivo = self.destino_actual - pos
        dist_meta = np.linalg.norm(vec_objetivo)
        
        # Llegada al waypoint
        if dist_meta < 0.5:
            if self.plan_maestro: self.plan_maestro.pop(0); self.destino_actual = self.plan_maestro[0] if self.plan_maestro else None
            return

        fuerza = np.zeros(2)
        
        # 1. ATRACCIÓN PURA (Sin ruido aleatorio fuerte)
        if dist_meta > 0: 
            # Vector director hacia la meta (Normalizado)
            direccion = vec_objetivo / dist_meta
            fuerza += direccion * 2.0 

        # 2. PAREDES (Solo si estoy MUY cerca)
        xi, yi = int(pos[0]), int(pos[1])
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                nx, ny = xi+dx, yi+dy
                if 0 <= nx < ANCHO and 0 <= ny < ALTO and self.model.mapa_muros[nx, ny] == 1:
                    vec_muro = pos - np.array([nx+0.5, ny+0.5])
                    d = np.linalg.norm(vec_muro) - 0.5 # Distancia a la superficie
                    
                    # Solo actúa si estoy a menos de 0.8 metros (antes era 1.5)
                    if d < RADIO_VISION_MUROS and d > 0.001:
                        # Fuerza exponencial suave
                        intensidad = FUERZA_PARED * np.exp(-d * 2) 
                        fuerza += (vec_muro/d) * intensidad

        # 3. SOCIAL (Evitar choques con otros)
        # Aquí sí mantenemos un pelín de ruido para evitar empates perfectos (Deadlocks)
        vecinos = self.model.space.get_neighbors(self.pos, RADIO_PERSONAL, include_center=False)
        hay_vecinos_cerca = False
        
        for v in vecinos:
            if hasattr(v, 'evacuado') and v.evacuado: continue
            
            vec_alej = pos - np.array(v.pos)
            dist = np.linalg.norm(vec_alej)
            dist_piel = dist - (RADIO_FISICO * 2)
            
            hay_vecinos_cerca = True

            # Protección matemática
            if dist < 0.001: 
                fuerza += np.random.uniform(-1, 1, 2) # Desempate técnico
                continue

            if dist < RADIO_PERSONAL:
                 push = 1.5 * np.exp(-dist_piel)
                 fuerza += (vec_alej / dist) * push

        # 4. RUIDO MÍNIMO (Solo si hay gente, para no vibrar estando solo)
        if hay_vecinos_cerca:
            fuerza += np.random.uniform(-RUIDO_BASE, RUIDO_BASE, 2)

        # 5. INTEGRACIÓN FÍSICA (Limitadores)
        norm_f = np.linalg.norm(fuerza)
        if norm_f > FUERZA_MAXIMA: fuerza = (fuerza / norm_f) * FUERZA_MAXIMA

        # INERCIA (Esto suaviza la trayectoria)
        # 80% inercia, 20% nueva fuerza -> Giro muy suave
        self.velocidad_actual = (self.velocidad_actual * 0.8) + (fuerza * 0.2)
        
        # CAP DE VELOCIDAD
        speed = np.linalg.norm(self.velocidad_actual)
        if speed > VELOCIDAD_BASE:
            self.velocidad_actual = (self.velocidad_actual / speed) * VELOCIDAD_BASE

        # MOVIMIENTO FINAL
        nueva_pos = pos + self.velocidad_actual
        if self.model.es_transitable(nueva_pos):
            self.model.space.move_agent(self, tuple(nueva_pos))
        else:
            # Si choca, desliza (elimina el componente normal a la pared)
            # Simplificado: se detiene un instante (absorbe energía)
            self.velocidad_actual *= 0.1

# --- 4. VISUALIZACIÓN ---
model = ModeloIntencion()

fig, ax = plt.subplots(figsize=(10, 7), facecolor='#101010')
ax.set_facecolor('#101010')

# Fondo
lineas_x, lineas_y = [], []
for x in range(ANCHO): lineas_x.extend([x, x, None]); lineas_y.extend([0, ALTO, None])
for y in range(ALTO): lineas_x.extend([0, ANCHO, None]); lineas_y.extend([y, y, None])
ax.plot(lineas_x, lineas_y, c='#004400', linewidth=0.5, alpha=0.3)
ax.imshow(model.mapa_muros.T, cmap=plt.cm.gray, origin='lower', alpha=0.9, extent=[0, ANCHO, 0, ALTO])

zona_salida = Circle(HITOS['SALIDA'], RADIO_ZONA_SALIDA, color='lime', alpha=0.2, zorder=1)
ax.add_patch(zona_salida)
ax.text(HITOS['SALIDA'][0], HITOS['SALIDA'][1], "EXIT", color='lime', ha='center', fontweight='bold', zorder=2)

lineas_grafo = []
for u, v in model.grafo_logico.edges():
    p1, p2 = HITOS[u], HITOS[v]
    l, = ax.plot([p1[0], p2[0]], [p1[1], p2[1]], c='#00FFFF', linewidth=1, alpha=0.4, zorder=3)
    lineas_grafo.append(l)

# Elementos Visuales
circulos_fisicos = []
circulos_personales = []
lineas_rastro = [] 
lineas_intencion = [] 

# LISTA PARA GUARDAR LOS CÍRCULOS DE FUEGO Y PODER DEVOLVERLOS
artistas_fuego = []

for _ in range(len(model.todos_los_agentes)):
    lr, = ax.plot([], [], c='yellow', linewidth=0.8, alpha=0.5, zorder=9)
    lineas_rastro.append(lr)
    
    li, = ax.plot([], [], c='white', linestyle=':', linewidth=1.0, alpha=0.7, zorder=9)
    lineas_intencion.append(li)

    cp = Circle((0,0), RADIO_PERSONAL, facecolor='#0088FF', alpha=0.2, zorder=10, visible=False)
    ax.add_patch(cp)
    circulos_personales.append(cp)
    cf = Circle((0,0), RADIO_FISICO, facecolor='orange', edgecolor='black', zorder=11, visible=False)
    ax.add_patch(cf)
    circulos_fisicos.append(cf)

texto_info = ax.text(2, ALTO-2, "", color="white", fontsize=12, zorder=20)
ax.axis('off')

cid = fig.canvas.mpl_connect('button_press_event', lambda e: model.crear_fuego(e.xdata, e.ydata) if e.xdata else None)

def init():
    return circulos_fisicos + circulos_personales + lineas_rastro + lineas_intencion + lineas_grafo + [texto_info, zona_salida] + artistas_fuego

def update(frame):
    model.step()
    
    agentes_activos = 0
    
    for i, agente in enumerate(model.todos_los_agentes):
        
        lineas_rastro[i].set_data(agente.traza_x, agente.traza_y)
        lineas_rastro[i].set_visible(True)

        if not agente.evacuado:
            pos = agente.pos
            circulos_fisicos[i].center = pos
            circulos_fisicos[i].set_visible(True)
            circulos_personales[i].center = pos
            circulos_personales[i].set_visible(True)
            
            if agente.destino_actual is not None:
                lineas_intencion[i].set_data([pos[0], agente.destino_actual[0]], 
                                             [pos[1], agente.destino_actual[1]])
                lineas_intencion[i].set_visible(True)
            else:
                lineas_intencion[i].set_visible(False)
            
            agentes_activos += 1
        else:
            circulos_fisicos[i].set_visible(False)
            circulos_personales[i].set_visible(False)
            lineas_intencion[i].set_visible(False)
            
    # Grafo
    if model.fuegos:
        for i, (u, v) in enumerate(model.grafo_logico.edges()):
            peso = model.grafo_logico[u][v]['weight']
            color = 'red' if peso > 2000 else '#00FFFF'
            width = 2 if peso > 2000 else 1
            lineas_grafo[i].set_color(color)
            lineas_grafo[i].set_linewidth(width)
    
    # FUEGO (Visualización Correcta para Blit)
    # Comprobamos si hay fuegos nuevos que no hemos dibujado
    # Sabemos que cada fuego usa 2 circulos (nucleo y aura)
    while len(artistas_fuego) < len(model.fuegos) * 2:
        # Indice del nuevo fuego
        idx_fuego = len(artistas_fuego) // 2
        f = model.fuegos[idx_fuego]
        
        # Crear circulos
        nucleo = Circle(tuple(f['pos']), f['radio'] * 0.5, color='red', alpha=0.9, zorder=5)
        aura = Circle(tuple(f['pos']), f['radio'], color='orange', alpha=0.3, zorder=4)
        
        ax.add_patch(nucleo)
        ax.add_patch(aura)
        
        # Añadir a la lista de artistas para devolver
        artistas_fuego.append(nucleo)
        artistas_fuego.append(aura)
    
    texto_info.set_text(f"Evacuados: {model.evacuados} | En Planta: {agentes_activos}")
    
    # ¡AQUÍ ESTÁ LA CLAVE! Devolvemos también los fuegos en la lista
    return circulos_fisicos + circulos_personales + lineas_rastro + lineas_intencion + lineas_grafo + [texto_info] + artistas_fuego

ani = animation.FuncAnimation(fig, update, frames=600, init_func=init, interval=30, blit=True)
plt.show()