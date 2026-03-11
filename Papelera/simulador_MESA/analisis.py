import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuración de estilo visual para gráficos profesionales
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 12})

def cargar_datos(archivo="metricas_evacuacion.csv"):
    try:
        df = pd.read_csv(archivo)
        return df
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{archivo}'. Ejecuta la simulación primero.")
        return None

def analizar_tiempos_evacuacion(df):
    """Analiza y grafica el tiempo que tardó cada agente y la curva global."""
    # Filtrar solo los eventos de evacuación exitosa
    df_evac = df[df['Evento'] == 'EVACUACION_COMPLETA'].copy()
    
    if df_evac.empty:
        print("No hay datos de evacuación completa.")
        return

    # 1. Histograma: Distribución de tiempos
    plt.figure(figsize=(10, 5))
    sns.histplot(df_evac['Step'], bins=15, kde=True, color='blue')
    plt.title("Distribución de Tiempos de Evacuación Individual (IET)")
    plt.xlabel("Tiempo (Steps de Simulación)")
    plt.ylabel("Número de Agentes")
    plt.axvline(df_evac['Step'].mean(), color='red', linestyle='dashed', linewidth=2, label=f'Media: {df_evac["Step"].mean():.1f}')
    plt.legend()
    plt.tight_layout()
    plt.show()

    # 2. Curva de Evacuación (Métrica estándar en la literatura)
    df_evac = df_evac.sort_values(by='Step')
    df_evac['Evacuados_Acumulados'] = range(1, len(df_evac) + 1)
    
    plt.figure(figsize=(10, 5))
    plt.plot(df_evac['Step'], df_evac['Evacuados_Acumulados'], marker='o', linestyle='-', color='green')
    plt.title("Curva Global de Evacuación")
    plt.xlabel("Tiempo (Steps)")
    plt.ylabel("Agentes Evacuados (Acumulado)")
    plt.fill_between(df_evac['Step'], df_evac['Evacuados_Acumulados'], color='green', alpha=0.2)
    plt.tight_layout()
    plt.show()

def analizar_estabilidad_algoritmo(df):
    """Analiza la 'Robustez vs Agilidad' contando recalculos y cambios de ruta."""
    # Contar eventos por agente
    df_cambios = df[df['Evento'] == 'CAMBIO_RUTA'].groupby('AgenteID').size().reset_index(name='Num_Cambios')
    df_recalculos = df[df['Evento'] == 'RECALCULO'].groupby('AgenteID').size().reset_index(name='Num_Recalculos')
    
    # Combinar en un solo DataFrame para comparar
    resumen_agentes = pd.merge(df_cambios, df_recalculos, on='AgenteID', how='outer').fillna(0)
    
    print("\n--- RESUMEN DE ESTABILIDAD DEL ALGORITMO ---")
    print(f"Promedio de Cambios de Ruta por Agente: {resumen_agentes['Num_Cambios'].mean():.2f}")
    print(f"Promedio de Recálculos por Fuego/Peligro: {resumen_agentes['Num_Recalculos'].mean():.2f}")
    
    # Gráfico de Barras: Estabilidad por Agente
    plt.figure(figsize=(12, 5))
    
    # Crear un gráfico de barras apiladas o agrupadas
    resumen_melted = pd.melt(resumen_agentes, id_vars=['AgenteID'], value_vars=['Num_Cambios', 'Num_Recalculos'])
    sns.barplot(data=resumen_melted, x='AgenteID', y='value', hue='variable', palette=['#FFA500', '#FF4500'])
    
    plt.title("Estabilidad de Ruta: Cambios vs Recálculos por Agente")
    plt.xlabel("ID del Agente")
    plt.ylabel("Cantidad de Eventos")
    plt.legend(title="Tipo de Evento", labels=['Cambios de Ruta (Agilidad)', 'Pánicos/Recálculos'])
    plt.tight_layout()
    plt.show()

def mapa_calor_recalculos(df):
    """Muestra EN QUÉ PARTE DEL MAPA los agentes deciden cambiar de ruta."""
    df_eventos_criticos = df[df['Evento'].isin(['CAMBIO_RUTA', 'RECALCULO', 'FUEGO_CREADO'])]
    
    if df_eventos_criticos.empty:
        return

    plt.figure(figsize=(10, 6))
    
    # Dibujar fuegos como estrellas rojas
    fuegos = df[df['Evento'] == 'FUEGO_CREADO']
    plt.scatter(fuegos['Pos_X'], fuegos['Pos_Y'], c='red', marker='*', s=300, label='Fuego Creado', zorder=5)

    # Densidad de recalculos (dónde se lo piensan)
    recalculos = df[df['Evento'] == 'CAMBIO_RUTA']
    sns.kdeplot(x=recalculos['Pos_X'], y=recalculos['Pos_Y'], cmap="YlOrBr", fill=True, alpha=0.6, label='Zonas de Cambio de Ruta')
    
    plt.title("Mapa de Calor Espacial: Decisiones Críticas y Cuellos de Botella")
    plt.xlabel("Coordenada X")
    plt.ylabel("Coordenada Y")
    plt.xlim(0, 40)
    plt.ylim(0, 25)
    
    # Añadir un grid suave para ubicarnos
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.show()

# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    df_metricas = cargar_datos()
    
    if df_metricas is not None:
        print("Datos cargados correctamente. Generando métricas...")
        analizar_tiempos_evacuacion(df_metricas)
        analizar_estabilidad_algoritmo(df_metricas)
        mapa_calor_recalculos(df_metricas)