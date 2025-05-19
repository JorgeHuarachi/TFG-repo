# ESTOS SERIAN LAS VARAIBLES QUE QUIZAS PUEDA MEDIR

    'Air temperature': "ºC", 
    'Air humidity': "%", 
    'Barometric pressure':"Pa",
    'Battery voltage': "V", 
    'Activity counter': "counts", 
    'Ambient light (visible + infrared)': "adim", 
    'Total VOC': "ppb", 
    'CO2 concentration': "ppm", 
    'Illuminance': "lx",
    'Ambient light (infrared)': "adim", 
    'Unknown': "Unknown", 
    'CO2 sensor status': "adim", 
    'Raw IR reading': "adim",
    'Indoor Air Quality': "adim", 
    'Indoor Air Quality calibration': "adim", 
    'PIR count': "counts", 
    'Ambient light': "counts",
    'Light intensity': "%", 
    'airQuality': "adim", 
    'Occupancy':"counts",
    'Battery level' : "%"

# CONDICIONES DE PELIGRO (de los que pienso que hay, solo tomando en cuenta el valor undividual de una varaible)

Estas condiciones de peligro toman en cuenta dos cosas importantes.
1. Que el valor de la varaible sea superior al aceptable
2. El tiempo estimado de exposición a en esa condición

Esto lo hago asi porque es cierto que unas condicione pueden clasificarse de peligrosas, poco peligrosas, ligeramente peligrosas en función de si pasar o no por una zona significe muy poco o mucho tiempo de exposición

## Temperatura (> 50°C) o Estrés Térmico (WBGT > 30°C)
Efecto: El calor extremo puede causar quemaduras, deshidratación o golpe de calor.

tiempo de exposición máximo:
Temperatura 50-60°C o WBGT 30-32°C: 2-3 minutos. Puedes atravesar si te toma menos de 3 minutos, pero evita el contacto con superficies calientes.
Temperatura 60-70°C o WBGT 32-35°C: 1 minuto. El riesgo de quemaduras y golpe de calor aumenta rápidamente; cruza solo si puedes hacerlo en menos de 60 segundos.
Temperatura > 70°C o WBGT > 35°C: 30 segundos o menos. Las quemaduras y el colapso por calor son casi inmediatos; evita este pasillo.

Recomendación: Si el pasillo está caliente, cúbrete con ropa (mangas largas, si es posible) para proteger la piel y mueve rápido.

## Dióxido de Carbono (CO₂ > 5,000 ppm)
Efecto: Causa hiperventilación, desorientación y fatiga.

Tiempo de exposición máximo:
CO₂ 5,000-10,000 ppm: 5-10 minutos. Puede causar dificultad para respirar, pero es tolerable por un tiempo breve.
CO₂ > 10,000 ppm: 2-3 minutos. El riesgo de desorientación aumenta; cruza en menos de 3 minutos.

Recomendación: Respira de manera controlada y evita esfuerzos físicos intensos.


## Temperatura (> 50°C) o Estrés Térmico (WBGT > 30°C)

# CONDICIONES DE PELIGRO (de los que no hay)

## Monóxido de Carbono (CO > 50 ppm)
Efecto: El CO es un gas tóxico que reemplaza el oxígeno en la sangre, causando mareos, náuseas y pérdida de conciencia.

Tiempo de exposición máximo:
CO 50-100 ppm: 10-15 minutos. Puedes atravesar el pasillo si te toma menos de 10 minutos, pero evita exposiciones prolongadas.
CO 100-200 ppm: 2-5 minutos. El riesgo de síntomas graves (mareos, desorientación) aumenta después de 2 minutos; cruza rápidamente.
CO > 200 ppm: 1 minuto o menos. Concentraciones superiores a 200 ppm pueden ser letales en minutos; solo atraviesa si puedes hacerlo en menos de 60 segundos.

Recomendación: Mantén la respiración controlada (inhala poco y exhala lentamente) y agáchate, ya que el CO tiende a acumularse en niveles superiores del aire.

## Falta de Oxígeno (O₂ < 19.5%)
Efecto: Niveles de oxígeno por debajo del 19.5% pueden causar mareos, desorientación y pérdida de conciencia.

Tiempo de exposición máximo:
O₂ entre 17-19.5%: 5 minutos. Puedes atravesar el pasillo si te toma menos de 5 minutos, pero debes moverte rápido y evitar esfuerzos físicos intensos (como correr, que aumenta la demanda de oxígeno).
O₂ entre 12-17%: 1-2 minutos. El riesgo de desorientación aumenta rápidamente; solo atraviesa si puedes hacerlo en menos de 2 minutos.
O₂ < 12%: 30 segundos o menos. La pérdida de conciencia puede ocurrir en menos de 1 minuto; evita este pasillo a menos que sea absolutamente necesario y puedas cruzarlo en segundos.

Recomendación: Si el oxígeno está por debajo del 19.5%, intenta contener la respiración por breves momentos o usar un pañuelo húmedo para reducir la inhalación de aire contaminado.

## Sulfuro de Hidrógeno (H₂S > 10 ppm)
Efecto: El H₂S es altamente tóxico y puede causar colapso respiratorio, irritación y pérdida de conciencia.

Tiempo de exposición máximo:
H₂S 10-20 ppm: 5 minutos. Puede causar irritación, pero es tolerable por un tiempo breve; cruza en menos de 5 minutos.
H₂S 20-50 ppm: 1-2 minutos. El riesgo de síntomas graves (dificultad para respirar, desmayo) aumenta rápidamente.
H₂S > 50 ppm: 30 segundos o menos. Concentraciones superiores a 50 ppm pueden ser letales en minutos; evita este pasillo a menos que puedas cruzarlo en segundos.

Recomendación: Si detectas olor a huevos podridos (H₂S), intenta contener la respiración mientras cruzas.

## Gases Inflamables (Metano, Propano, etc. > 10% del LEL)
Efecto: Riesgo de explosión si se alcanza el límite de explosividad.

Tiempo de exposición máximo:
10-25% del LEL: 5 minutos. El riesgo de explosión es bajo, pero aumenta con el tiempo si hay fuentes de ignición (chispas, calor). Cruza rápidamente.
25-50% del LEL: 1-2 minutos. El riesgo de explosión es significativo; solo atraviesa si puedes hacerlo en menos de 2 minutos y no hay fuentes de ignición visibles.
50% del LEL: Evita a toda costa. El riesgo de explosión es inminente; no uses este pasillo, independientemente del tiempo.

Recomendación: Apaga cualquier dispositivo eléctrico (linternas, radios) para evitar chispas mientras cruzas.

## Amoníaco (NH₃ > 25 ppm)
Efecto: Irritación severa en ojos, garganta y pulmones.

Tiempo de exposición máximo:
NH₃ 25-50 ppm: 2-3 minutos. Puede causar irritación, pero es tolerable por un tiempo breve.
NH₃ > 50 ppm: 1 minuto o menos. La irritación severa puede dificultar la respiración y la visión.

Recomendación: Cierra los ojos parcialmente y usa un pañuelo para cubrir la cara mientras cruzas.

## Radiación (> 1 mSv/h)
Efecto: Daño celular acumulativo, riesgo de cáncer a largo plazo.

Tiempo de exposición máximo:
1-5 mSv/h: 5 minutos. La exposición breve no causa daño inmediato, pero se acumula con el tiempo.
5 mSv/h: 1 minuto o menos. Evita este pasillo si puedes; el daño puede ser significativo incluso en exposiciones cortas.

Recomendación: Si no hay otra opción, cruza rápido y busca atención médica después de la evacuación.













