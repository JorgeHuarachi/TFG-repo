import numpy as np
import matplotlib.pyplot as plt

def verificar_diseño():
    # --- 1. CONFIGURACIÓN DEL ESPACIO (Tus datos) ---
    ANCHO, ALTO = 40, 25
    
    # HITOS
    HITOS = {
     'h1': (6.5, 20),
     'h2': (4, 8),
     'h3': (14, 2.5),
     'h4': (24, 2.5),
     'h5': (33.5, 8),
     'h6': (26, 20),
     'h7': (18, 10.5),
     '12': (4, 16),
     '23': (8, 2.5),
     '27': (8, 10),
     '37': (13, 5),
     '47': (20, 2.5),
     '57': (24, 5),
     '45': (28, 2.5),
     '88': (28, 11),
     '89': (10.5, 16),
     '16': (13, 20),
     '76': (19, 16),
     '99': (33, 16),
     'VENTANA': (39, 10),
     'SALIDA': (39, 20.5),
}   

     # AGENTES
    posiciones = [(3, 19), (9, 21), (5, 13), (2, 4), (11, 3), (19, 1), (25, 3), (22, 3), (12, 13), (14, 9), (22, 12), (31, 18), (34, 21), (31, 10), (31, 4), (5, 1), (1, 23)]
    # --- 2. CONSTRUCCIÓN DE MUROS (Tu código exacto) ---
    mapa_muros = np.zeros((40, 25))
    mapa_muros[0,:] = 1; mapa_muros[-1,:] = 1
    mapa_muros[:,0] = 1; mapa_muros[:,-1] = 1
    mapa_muros[0:40, 0] = 1
    mapa_muros[39, 0:25] = 1
    mapa_muros[0:40, 24] = 1
    mapa_muros[0, 0:25] = 1
    mapa_muros[0:39, 16] = 1
    mapa_muros[28, 1:17] = 1
    mapa_muros[8, 0:17] = 1
    mapa_muros[20, 0:6] = 1
    mapa_muros[13, 16:24] = 1
    mapa_muros[3:6, 16] = 0
    mapa_muros[8, 9:12] = 0
    mapa_muros[8, 2:4] = 0
    mapa_muros[20, 2:4] = 0
    mapa_muros[28, 2:4] = 0
    mapa_muros[12:15, 5] = 0
    mapa_muros[28, 10:13] = 0
    mapa_muros[13, 19:22] = 0
    mapa_muros[10:12, 16] = 0
    mapa_muros[18:20, 16] = 0
    mapa_muros[32:35, 16] = 0
    mapa_muros[39, 19:23] = 0
    mapa_muros[39, 9:12] = 0

    # --- 3. VISUALIZACIÓN ---
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Dibujamos el mapa (Usamos .T para trasponer ejes y que coincida X con horizontal)
    ax.imshow(mapa_muros.T, cmap='Greys', origin='lower', extent=[0, ANCHO, 0, ALTO])
    
    # Dibujamos HITOS
    print("--- VERIFICACIÓN DE COLISIONES ---")
    for nombre, (x, y) in HITOS.items():
        # Chequeo de seguridad
        ix, iy = int(x), int(y)
        if 0 <= ix < ANCHO and 0 <= iy < ALTO:
            if mapa_muros[ix, iy] == 1:
                print(f"⚠️ ALERTA: El Hito '{nombre}' cae DENTRO de un muro en ({ix}, {iy})")
        
        ax.plot(x, y, 'go', markersize=8, markeredgecolor='black', zorder=5)
        ax.text(x, y+0.5, nombre, color='green', fontweight='bold', ha='center', fontsize=8, zorder=6)

    # Dibujamos AGENTES
    pos_x = [p[0] for p in posiciones]
    pos_y = [p[1] for p in posiciones]
    ax.scatter(pos_x, pos_y, c='blue', s=60, label='Agentes', edgecolors='white', zorder=7)
    
    # Configuración final
    ax.set_title("Verificación del Mapa, Hitos y Agentes")
    ax.set_xlabel("Coordenada X")
    ax.set_ylabel("Coordenada Y")
    ax.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    ax.set_xticks(np.arange(0, ANCHO+1, 2))
    ax.set_yticks(np.arange(0, ALTO+1, 2))
    
    # Leyenda visual
    from matplotlib.lines import Line2D
    leyenda = [
        Line2D([0], [0], marker='s', color='w', markerfacecolor='black', label='Muro', markersize=10, markeredgecolor='k'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='green', label='Hito/Puerta', markersize=10, markeredgecolor='k'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', label='Agente', markersize=10, markeredgecolor='k')
    ]
    ax.legend(handles=leyenda, loc='upper right')

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    verificar_diseño()