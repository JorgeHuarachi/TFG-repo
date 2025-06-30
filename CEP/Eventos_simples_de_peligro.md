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

## **MIS EVENTOS SIMPLES (PARAMETROS QUE QUIZAS TENGO)**

    Parámetro	Nombre (Display)	Unidad	Descripción 

    co2	CO₂	ppm	Nivel de dióxido de carbono en el aire. Indica la calidad de ventilación.
    iaq	Indoor Air Quality	adim	Índice estimado de calidad del aire. Basado en gases, humedad, CO₂, etc.
    calib_iaq	Indoor Air Quality calibration	adim	Valor interno del sensor para calibrar el IAQ. No es directamente útil para alertas.
    tvoc	TVOC	ppb	Compuestos Orgánicos Volátiles Totales. Indican presencia de químicos en el aire.
    air_temperature	Air Temperature	°C	Temperatura del aire ambiente.
    air_humidity	Air Humidity	%	Humedad relativa del aire. Afecta confort, riesgo de moho o estrés térmico.
    barometric_pressure	Barometric Pressure	hPa	Presión atmosférica. Útil para detectar cambios bruscos en el entorno (explosión, fuga, etc.).
    pir_count	PIR Count	counts	Cuenta de detección por sensor PIR (movimiento). Indica si hay presencia reciente.
    ambient_light	Ambient Light	counts	Cantidad de luz ambiental (luminosidad). Útil para saber si hay luz natural o artificial.
    battery_voltage	Battery Voltage	V	Voltaje de la batería del sensor. Útil para monitorear salud del dispositivo.

## EVENTOS SIMPLES

### Dóxido de Carbono (CO₂ > 1,000 ppm)

Efecto: Afecta la capacidad cognitiva, provoca fatiga, cefaleas, desorientación y en niveles altos, pérdida de conciencia.

Tiempo de exposición máximo:

1,000-2,000 ppm: 10-30 minutos. Puede causar somnolencia y reducción del rendimiento cognitivo. Puedes pasar brevemente.
2,000-5,000 ppm: 5-10 minutos. Riesgo de fatiga, dolor de cabeza, sensación de encierro. Evita exposiciones prolongadas.
5,000 ppm: 2-3 minutos. Puede causar hiperventilación y desorientación; atraviesa rápidamente.

Recomendación: Mejora la ventilación si es posible. Cruza sin correr y mantén la calma para no hiperventilar.


### Calidad del Aire Interior (IAQ > 100 adim)

Efecto: Indicador compuesto de contaminación; valores altos significan aire viciado o contaminado.

Tiempo de exposición máximo:

100-150 adim: 10-20 minutos. Disminuye la calidad del aire, puede causar molestias respiratorias leves.
150 adim: 5 minutos. Riesgo de irritación o malestar para personas sensibles. Evita zonas con IAQ > 150.

Recomendación: Usa mascarilla si está disponible. Ventila si es posible.


### Compuestos Orgánicos Volátiles (TVOC > 500 ppb)

Efecto: Provoca irritación ocular, dolor de cabeza, daños hepáticos, y algunos son cancerígenos a largo plazo.

Tiempo de exposición máximo:

500-1,000 ppb: 10 minutos. Leve irritación para personas sensibles.
1,000-3,000 ppb: 3-5 minutos. Aumenta el riesgo de malestar; atraviesa rápido.
3,000 ppb: 1-2 minutos. Riesgo alto de toxicidad, evita esta zona o usa protección respiratoria.

Recomendación: Usa mascarilla con filtro químico si es posible. No permanezcas en el área.

### Temperatura (Air Temperature)

Valor actual: 20.19°C (normal)

Efecto: Bajo 15°C puede causar hipotermia en exposiciones largas. Sobre 30°C puede generar fatiga térmica.

Tiempo de exposición máximo (en caso de anomalías):

<10°C: 30 minutos sin abrigo. Puede causar temblores o entumecimiento.
30°C: 15 minutos. Aumenta el riesgo de deshidratación.

Recomendación: Actualmente en valores seguros. Observar si cambia.

### Humedad del aire (> 70% o < 30%)

Efecto: Afecta la capacidad del cuerpo para enfriarse. Alta humedad evita evaporación del sudor; baja reseca mucosas.

Tiempo de exposición máximo:

70-80%: 10-15 minutos. Incomoda la respiración, puede generar fatiga.
80%: 5 minutos. Riesgo de golpe de calor si la temperatura es alta.

Recomendación: Ventila o usa deshumidificadores si puedes. Actualmente está en un rango saludable (55%).

### Presión barométrica (Barometric Pressure)

Valor actual: 947.18 hPa (bajo)

Efecto: Puede indicar tormentas o baja disponibilidad de oxígeno en altitudes. Personas sensibles pueden tener cefaleas.

Recomendación: No es riesgosa en sí misma, pero si hay otros síntomas acompañantes (mareos), monitorear.

### Movimiento detectado (PIR count > 0)

Efecto: Indica presencia/movimiento de personas. No tiene riesgo en sí, pero puede ser clave para activar otros eventos (intrusión, presencia humana en zona peligrosa).

### Luz ambiente (Ambient Light)

Valor actual: 164 (bajo-moderado)

Efecto: Niveles muy bajos pueden causar caídas, fatiga visual. No se considera peligroso por sí mismo.

### Voltaje de batería

Valor actual: 3.71V

Efecto: Solo relevante para asegurar que el sensor funcione correctamente. No afecta a las personas directamente.

Calibración IAQ

Valor actual: 0 (sin calibrar)

Comentario: La falta de calibración puede afectar la precisión del valor de IAQ. Se recomienda calibración periódica para mantener la fiabilidad del sistema.

## ontología de los sensores de evacuación
