

#  Guía de Instalación y Despliegue

Sigue estos pasos para clonar el repositorio, configurar un entorno virtual aislado y ejecutar los motores de simulación (EvacEngine y SpatialEngine) en tu máquina local.

## 1. Clonar el repositorio
Abre tu terminal y descarga el código fuente usando Git:
```bash
git clone [https://github.com/TU_USUARIO/TU_REPOSITORIO.git](https://github.com/TU_USUARIO/TU_REPOSITORIO.git)
cd TU_REPOSITORIO

```

## 2. Crear y activar el Entorno Virtual

Es una buena práctica aislar las dependencias del proyecto utilizando un entorno virtual (`venv`). Ejecuta los siguientes comandos en la terminal (preferiblemente integrada en VSCode):

**Generar el entorno:**

```bash
python -m venv .venv

```

**Activar el entorno:**

* **Windows (CMD / PowerShell):**
```bash
.\.venv\Scripts\activate

```


* **macOS / Linux:**
```bash
source .venv/bin/activate

```



*(Sabrás que ha funcionado si ves `(.venv)` al principio de la línea de tu terminal).*

## 3. Instalar Dependencias

Una vez activado el entorno, instala todas las librerías científicas necesarias (`mesa`, `shapely`, `networkx`, `pandas`, etc.) ejecutando:

```bash
pip install -r requirements.txt

```

*(Nota: Asegúrate de tener `pip` actualizado. Puedes actualizarlo con `python -m pip install --upgrade pip`)*.

---

### Mantenimiento 

Si durante el desarrollo instalas nuevas librerías (ej. `pip install nueva_libreria`), recuerda actualizar el archivo de dependencias antes de hacer el *commit* para que tu equipo (o tu futuro yo) lo tenga sincronizado:

```bash
pip freeze > requirements.txt

```
