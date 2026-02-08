import numpy as np
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, Patch

# -----------------------------------------------------------------------------
# 1. Configuración y Geometría Estática
# -----------------------------------------------------------------------------
def create_room_mesh(x_c, y_c, w, h, color):
    # Suelo con un poco de grosor visual simulado
    return go.Mesh3d(
        x=[x_c-w/2, x_c+w/2, x_c+w/2, x_c-w/2],
        y=[y_c-h/2, y_c-h/2, y_c+h/2, y_c+h/2],
        z=[0, 0, 0, 0],
        color=color, opacity=0.5,
        i=[0,0], j=[1,2], k=[2,3],
        hoverinfo='skip'
    )

# Generar rutas suaves (Interpolación)
def interpolar_ruta(puntos, pasos=10):
    ruta_suave = []
    for i in range(len(puntos) - 1):
        inicio = np.array(puntos[i])
        fin = np.array(puntos[i+1])
        x_vals = np.linspace(inicio[0], fin[0], pasos)
        y_vals = np.linspace(inicio[1], fin[1], pasos)
        for x, y in zip(x_vals, y_vals):
            ruta_suave.append((x, y))
    return ruta_suave

# Rutas de ejemplo
ruta_raw_1 = [(0,0), (1,0), (2,0), (3,0), (4,0), (5,0), (6,0), (6,1), (6,0), (3,0), (0,0)]
ruta_raw_2 = [(6,2), (5,2), (4,2), (3,0), (2,-1), (1,-1), (0,0), (1,1), (3,0), (6,2)]

# Creamos rutas con muchos puntos intermedios
ruta_1 = interpolar_ruta(ruta_raw_1, pasos=15)
ruta_2 = interpolar_ruta(ruta_raw_2, pasos=15)

# -----------------------------------------------------------------------------
# 2. Montar la Figura Inicial
# -----------------------------------------------------------------------------
fig = go.Figure()

# --- Escenario (Traces 0, 1, 2) ---
fig.add_trace(create_room_mesh(0, 0, 4, 4, 'blue'))   # Hab A
fig.add_trace(create_room_mesh(6, 0, 4, 4, 'green'))  # Hab B
fig.add_trace(create_room_mesh(3, 0, 2, 1, 'gray'))   # Pasillo

# --- Agente 1 (Rojo) ---
# Trace 3: El Rastro (Línea)
fig.add_trace(go.Scatter3d(
    x=[ruta_1[0][0]], y=[ruta_1[0][1]], z=[0.3], 
    mode='lines', line=dict(color='red', width=4), name='Rastro 1'
))
# Trace 4: La Bola (Marcador) - Z=0.3 para que toque el suelo (Radio aprox)
fig.add_trace(go.Scatter3d(
    x=[ruta_1[0][0]], y=[ruta_1[0][1]], z=[0.3],
    mode='markers', marker=dict(size=8, color='red'), name='Agente 1'
))

# --- Agente 2 (Azul) ---
# Trace 5: El Rastro
fig.add_trace(go.Scatter3d(
    x=[ruta_2[0][0]], y=[ruta_2[0][1]], z=[0.3],
    mode='lines', line=dict(color='blue', width=4), name='Rastro 2'
))
# Trace 6: La Bola
fig.add_trace(go.Scatter3d(
    x=[ruta_2[0][0]], y=[ruta_2[0][1]], z=[0.3],
    mode='markers', marker=dict(size=8, color='blue'), name='Agente 2'
))

# Configuración de cámara
fig.update_layout(
    scene=dict(
        aspectmode='data',
        camera=dict(eye=dict(x=0, y=-2, z=2))
    ),
    margin=dict(l=0, r=0, b=0, t=0),
    uirevision='constant_value' # CRUCIAL: Evita que la cámara se resetee
)

# -----------------------------------------------------------------------------
# 3. App Dash
# -----------------------------------------------------------------------------
app = Dash(__name__)

app.layout = html.Div([
    html.H2("Simulación Dash: Agentes y Rastros", style={'textAlign': 'center'}),
    
    html.Div([
        html.Button('Iniciar/Pausar', id='btn-play', n_clicks=0),
    ], style={'textAlign': 'center'}),

    dcc.Graph(id='3d-viewer', figure=fig),

    # Intervalo: 50ms = 20 FPS (Suficiente para Dash)
    dcc.Interval(id='interval-comp', interval=50, n_intervals=0, disabled=True),
    # Guardamos el índice actual del paso
    dcc.Store(id='step-store', data=0)
])

# Callback de Play/Pause
@app.callback(
    Output('interval-comp', 'disabled'),
    Input('btn-play', 'n_clicks'),
    State('interval-comp', 'disabled')
)
def toggle(n, disabled):
    return not disabled if n > 0 else True

# Callback Principal de Animación (Usando PATCH para velocidad)
@app.callback(
    [Output('3d-viewer', 'figure'),
     Output('step-store', 'data')],
    Input('interval-comp', 'n_intervals'),
    State('step-store', 'data')
)
def update_metrics(n, step):
    # Calcular índices circulares
    idx_1 = step % len(ruta_1)
    idx_2 = step % len(ruta_2)
    
    # Creamos un Patch (un parche parcial)
    patched_fig = Patch()
    
    # --- Actualizar Agente 1 ---
    x1, y1 = ruta_1[idx_1]
    # Mover bola (Trace 4)
    patched_fig.data[4].x = [x1]
    patched_fig.data[4].y = [y1]
    
    # Actualizar rastro (Trace 3) - Añadimos punto al final
    # Limitamos el rastro a los últimos 50 puntos para que no se ralentice con el tiempo
    # (Efecto "Cometa")
    current_trail_x = [p[0] for p in ruta_1[max(0, idx_1-50):idx_1+1]]
    current_trail_y = [p[1] for p in ruta_1[max(0, idx_1-50):idx_1+1]]
    current_trail_z = [0.3] * len(current_trail_x)
    
    patched_fig.data[3].x = current_trail_x
    patched_fig.data[3].y = current_trail_y
    patched_fig.data[3].z = current_trail_z

    # --- Actualizar Agente 2 ---
    x2, y2 = ruta_2[idx_2]
    # Mover bola (Trace 6)
    patched_fig.data[6].x = [x2]
    patched_fig.data[6].y = [y2]
    
    # Rastro (Trace 5)
    current_trail_x2 = [p[0] for p in ruta_2[max(0, idx_2-50):idx_2+1]]
    current_trail_y2 = [p[1] for p in ruta_2[max(0, idx_2-50):idx_2+1]]
    current_trail_z2 = [0.3] * len(current_trail_x2)
    
    patched_fig.data[5].x = current_trail_x2
    patched_fig.data[5].y = current_trail_y2
    patched_fig.data[5].z = current_trail_z2

    return patched_fig, step + 1

if __name__ == '__main__':
    app.run(debug=True)