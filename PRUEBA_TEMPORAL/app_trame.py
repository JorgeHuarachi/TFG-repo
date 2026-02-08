import asyncio
import numpy as np
import pyvista as pv
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, vtk

# -----------------------------------------------------------------------------
# 1. Configuración del Escenario
# -----------------------------------------------------------------------------
pv.OFF_SCREEN = True
plotter = pv.Plotter()

# Dibujamos las zonas (Suelos)
# Sala 1 (Roja): x de -2 a 2, y de -2 a 2
plotter.add_mesh(pv.Cube(center=(0,0,0), x_length=4, y_length=4, z_length=0.1), color="red", opacity=0.3, show_edges=True)
# Pasillo (Gris): x de 2 a 6, y de -1 a 1 (Más estrecho)
plotter.add_mesh(pv.Cube(center=(4,0,0), x_length=4, y_length=2, z_length=0.1), color="gray", opacity=0.3, show_edges=True)
# Sala 2 (Verde): x de 6 a 10, y de -2 a 2
plotter.add_mesh(pv.Cube(center=(8,0,0), x_length=4, y_length=4, z_length=0.1), color="green", opacity=0.3, show_edges=True)

# -----------------------------------------------------------------------------
# 2. Física Avanzada (Agentes + Paredes)
# -----------------------------------------------------------------------------
class SimuladorMultitudes:
    def __init__(self, num_agentes=50):
        self.dt = 0.05
        self.num = num_agentes
        
        # Posiciones iniciales solo en sala roja
        self.pos = np.random.rand(num_agentes, 2) * 3.0 - 1.5
        self.vel = np.zeros((num_agentes, 2))
        
        # Objetivos: [Puerta1, Puerta2, Meta]
        self.objetivos = [np.array([2.0, 0]), np.array([6.0, 0]), np.array([9.0, 0])]
        
        # Parámetros ajustados para mayor velocidad y reacción
        self.v_deseada = 3.5      # Más rápidos
        self.distancia_vision = 0.6 
        self.fuerza_repulsion = 40.0 # Se empujan fuerte
        self.fuerza_pared = 100.0    # La pared es intocable

    def calcular_fuerzas(self):
        fuerzas = np.zeros_like(self.pos)
        
        # --- 1. Atracción a Metas (Navegación básica) ---
        objetivos_actuales = np.zeros_like(self.pos)
        # Si estás a la izquierda de la entrada del pasillo (x<2), ve a la puerta 1
        mask_sala1 = self.pos[:, 0] < 2.0
        # Si estás en el pasillo, ve a la puerta 2
        mask_pasillo = (self.pos[:, 0] >= 2.0) & (self.pos[:, 0] < 6.0)
        # Si ya pasaste, ve al fondo
        mask_sala2 = self.pos[:, 0] >= 6.0
        
        objetivos_actuales[mask_sala1] = self.objetivos[0]
        objetivos_actuales[mask_pasillo] = self.objetivos[1]
        objetivos_actuales[mask_sala2] = self.objetivos[2]

        direccion = objetivos_actuales - self.pos
        distancia = np.linalg.norm(direccion, axis=1).reshape(-1, 1)
        
        with np.errstate(divide='ignore', invalid='ignore'):
            dir_norm = direccion / distancia
            dir_norm[distancia[:,0] == 0] = 0
        
        fuerza_meta = (dir_norm * self.v_deseada - self.vel) * 3.0
        fuerzas += fuerza_meta

        # --- 2. Repulsión entre Agentes ---
        diff = self.pos[:, np.newaxis, :] - self.pos[np.newaxis, :, :]
        dist_sq = np.sum(diff**2, axis=2)
        dist = np.sqrt(dist_sq)
        np.fill_diagonal(dist, np.inf)
        
        cercanos = dist < self.distancia_vision
        if np.any(cercanos):
            dist_segura = dist.copy()
            dist_segura[dist_segura < 0.01] = 0.01
            f_rep = self.fuerza_repulsion / (dist_segura**2)
            f_rep[~cercanos] = 0
            # Vectorizar fuerza
            fx = np.sum((diff[:,:,0] / dist_segura) * f_rep, axis=1)
            fy = np.sum((diff[:,:,1] / dist_segura) * f_rep, axis=1)
            fuerzas[:, 0] += fx
            fuerzas[:, 1] += fy

        # --- 3. Repulsión de Paredes (NUEVO) ---
        # Definimos límites físicos
        
        # A. Paredes Laterales Exteriores (Izquierda y Derecha global)
        # Si x < -1.8, empuja derecha
        fuerzas[self.pos[:, 0] < -1.8, 0] += self.fuerza_pared
        # Si x > 9.8, empuja izquierda
        fuerzas[self.pos[:, 0] > 9.8, 0] -= self.fuerza_pared

        # B. Paredes Superiores e Inferiores (Globales de las salas grandes)
        # Si y > 1.8 en salas (x < 2 o x > 6), empuja abajo
        en_salas = (self.pos[:, 0] < 2.0) | (self.pos[:, 0] > 6.0)
        fuerzas[(self.pos[:, 1] > 1.8) & en_salas, 1] -= self.fuerza_pared
        fuerzas[(self.pos[:, 1] < -1.8) & en_salas, 1] += self.fuerza_pared

        # C. Paredes del Pasillo (El estrechamiento)
        # Si estás en zona X de pasillo (aprox), Y no puede pasar de 1
        en_zona_pasillo = (self.pos[:, 0] > 1.8) & (self.pos[:, 0] < 6.2)
        fuerzas[(self.pos[:, 1] > 0.8) & en_zona_pasillo, 1] -= self.fuerza_pared * 2
        fuerzas[(self.pos[:, 1] < -0.8) & en_zona_pasillo, 1] += self.fuerza_pared * 2

        # D. Esquinas de las Puertas (Colisión vertical)
        # Si te chocas contra el muro al intentar entrar al pasillo
        # Muro izquierdo entrada (x aprox 2, y fuera de rango pasillo)
        choco_muro_entrada = (self.pos[:, 0] > 1.8) & (self.pos[:, 0] < 2.2) & (np.abs(self.pos[:, 1]) > 1.0)
        fuerzas[choco_muro_entrada, 0] -= self.fuerza_pared # Empuja atrás
        
        # Muro derecho salida (x aprox 6, y fuera de rango pasillo)
        choco_muro_salida = (self.pos[:, 0] > 5.8) & (self.pos[:, 0] < 6.2) & (np.abs(self.pos[:, 1]) > 1.0)
        fuerzas[choco_muro_salida, 0] += self.fuerza_pared # Empuja atrás

        return fuerzas

    def paso(self):
        acc = self.calcular_fuerzas()
        self.vel += acc * self.dt
        # Limite velocidad máxima
        speed = np.linalg.norm(self.vel, axis=1).reshape(-1, 1)
        mask_max = speed > 4.0
        if np.any(mask_max):
            self.vel[mask_max[:,0]] = (self.vel[mask_max[:,0]] / speed[mask_max[:,0]]) * 4.0
        self.pos += self.vel * self.dt
        return self.pos

# -----------------------------------------------------------------------------
# 3. Visualización
# -----------------------------------------------------------------------------
sim = SimuladorMultitudes(num_agentes=60) # Aumentamos agentes para ver el atasco

# Configuración Inicial
z_vals = np.full(sim.num, 0.3)
puntos_vtk = pv.PolyData(np.column_stack((sim.pos, z_vals)))
esfera_base = pv.Sphere(radius=0.2) # Bolas un poco más pequeñas para que quepan mejor
mesh_glifo = puntos_vtk.glyph(geom=esfera_base, scale=False)
actor_esferas = plotter.add_mesh(mesh_glifo, color="orange")

plotter.reset_camera()
plotter.view_xy()
plotter.camera.zoom(1.3)

# -----------------------------------------------------------------------------
# 4. Servidor
# -----------------------------------------------------------------------------
server = get_server()
state = server.state
is_running = False
my_ui_view = None 

async def animation_loop():
    global is_running
    while is_running:
        nuevas_pos = sim.paso()
        
        # Actualizar
        puntos_vtk.points[:, 0] = nuevas_pos[:, 0]
        puntos_vtk.points[:, 1] = nuevas_pos[:, 1]
        
        nuevo_mesh = puntos_vtk.glyph(geom=esfera_base, scale=False)
        actor_esferas.mapper.SetInputData(nuevo_mesh)
        
        plotter.render()
        if my_ui_view:
            my_ui_view.update()
        
        # Bajamos el tiempo de espera para intentar subir FPS
        await asyncio.sleep(0.01)

def toggle_animation():
    global is_running
    is_running = not is_running
    if is_running:
        asyncio.create_task(animation_loop())

def reset_sim():
    global sim
    sim = SimuladorMultitudes(num_agentes=60)
    puntos_vtk.points[:, 0] = sim.pos[:, 0]
    puntos_vtk.points[:, 1] = sim.pos[:, 1]
    nuevo_mesh = puntos_vtk.glyph(geom=esfera_base, scale=False)
    actor_esferas.mapper.SetInputData(nuevo_mesh)
    plotter.render()
    if my_ui_view: my_ui_view.update()

# -----------------------------------------------------------------------------
# 5. Layout (REMOTE VIEW)
# -----------------------------------------------------------------------------
with SinglePageLayout(server) as layout:
    layout.title.set_text("Evacuación con Paredes y Física")
    with layout.toolbar:
        vuetify3.VSpacer()
        vuetify3.VBtn("Iniciar / Pausa", click=toggle_animation, color="primary")
        vuetify3.VBtn("Reiniciar", click=reset_sim, color="error", classes="ml-4")
        vuetify3.VSpacer()
    with layout.content:
        with vuetify3.VContainer(fluid=True, classes="pa-0 fill-height", style="height: 100%; width: 100%;"):
            # Modo Remoto (Stream de vídeo) para que no se congele
            view = vtk.VtkRemoteView(plotter.render_window)
            my_ui_view = view

if __name__ == "__main__":
    server.start()