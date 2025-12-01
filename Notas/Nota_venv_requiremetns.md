 _Nota para alguien que recien clone este repoitorio en si ordenador local:_

**_Crear/activar entorno virtual_**
 
 Generar carpeta, ejecutando en la terminal _(la del VScode a ser posible)_: 
   
  `python -m  venv venv`
   
 Una vez creado, activalo, en al terminal: 

   Windows: `.\venv\scripts\activate`
   
   linux/mac: `source venv/bin/activate`
   
 _Deberia salir `(venv)` al principio de la linea de comandos de la terminal_

**_Gestionar dependencias_**
 
 **(Recuperar)** Instalar las librerias necesarias de golpe: `pip install -r requierements.txt` 
 
 **(Actalizar)** Si has instalado librerias nuevas (no es la primera vez que utilizas este repositorio), en la terminal: `pip freeze > requirements.txt`

 _Es posible que si es a primera vez que realizas esto comprueba que tienes pip `pip --version`, si no, instalalo o actualizalo **Windows:** `python -m ensurepip --upgrade`, **Linux:** `sudo apt install python3-pip`_. 


