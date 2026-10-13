# ha-axpert-max-twin

Integración personalizada de Home Assistant para el perfil USB HID capturado en un
Axpert MAX TWIN 11 kW. Compatible con repositorios personalizados de HACS. Solo consulta
el inversor: **QPIGS, QPIGS2, QMOD y QPIWS**. No incorpora controles ni comandos arbitrarios.

## Versiones

- **0.2.2:** traduce y agrupa todos los nombres, y limpia del registro las entidades
  de energía retiradas. [Cambios y actualización](docs/v0.2.2.md).
- **0.2.1:** corrigió los nombres nuevos y eliminó los ocho contadores de energía.
- **0.2.0:** añadió campos AC/red, modo, temperatura, alarmas y cálculos.
- **0.1.1:** respaldo con las 12 entidades originales y el intervalo configurable desde
  5 segundos. [Recuperar respaldo](https://github.com/Depintopinto/ha-axpert-max-twin/releases/tag/v0.1.1).

La comunicación de 0.1.1 funcionó físicamente en el equipo del usuario. Los campos
adicionales se contrastaron con las tramas capturadas; QPIWS nuevo aún necesita
comprobación física tras actualizar. No se declara compatibilidad con otros firmwares
solo por compartir el nombre MAX/TWIN o el VID:PID.

## Instalación y actualización

1. Detén WatchPower, `axpert_inverter`, mppsolar y otros clientes del mismo USB.
2. En HACS → Repositorios personalizados, añade
   `https://github.com/Depintopinto/ha-axpert-max-twin`, categoría **Integración**.
3. Descarga la integración y reinicia Home Assistant completo.
4. Añade **Axpert MAX TWIN** en Dispositivos y servicios y selecciona `/dev/hidrawN`.

La versión nueva conserva los identificadores de las 12 entidades originales y elimina
del registro las ocho entidades de energía obsoletas de esta integración. El intervalo
predeterminado es 5 segundos;
se cambia desde **Configurar** entre 5 y 3600 segundos.

Instalación manual: copia `custom_components/axpert_max_twin` a
`/config/custom_components/axpert_max_twin` y reinicia. Requiere Linux con hidraw y acceso
USB desde Core. Preparada para HA OS aarch64; no requiere dependencias USB binarias,
MQTT ni un add-on adicional.

## Sensores

Hay 25 sensores en un único dispositivo:

| Grupo lógico | Cantidad | Contenido |
|---|---:|---|
| Salida Red | 7 | Potencia activa, tensión, frecuencia, VA, carga %, corriente y factor de potencia calculados |
| Fotovoltaica | 7 | Seis valores PV1/PV2 y potencia total calculada |
| Batería | 4 | Tensión, carga, descarga y nivel comunicado |
| Entrada Red | 2 | Tensión y frecuencia |
| General | 5 | Código y modo, temperatura, alarmas y trama de diagnóstico |

Todos los nombres se muestran en español con el prefijo de su grupo, para que aparezcan
juntos al ordenarse. Los cálculos
solo aparecen cuando sus entradas son válidas: corriente = VA / V; factor de potencia =
W / VA. El consumo representa la salida AC informada por el inversor y no desglosa sus
dos salidas ni otros consumos de la vivienda. Las potencias PV son potencias de carga
comunicadas por el inversor. El modo y las alarmas usan etiquetas legibles.

La trama original QPIWS es una entidad de diagnóstico deshabilitada por defecto. Las
posiciones ambiguas del final de la respuesta se conservan sin asignar códigos de error.
Consulta [detalle de v0.2.2](docs/v0.2.2.md), [análisis de la captura](docs/capture-analysis.md)
y [análisis del fallo original](docs/upstream-analysis.md).

## USB y diagnósticos

Perfil observado: `0665:5161`, interfaz 0, interrupt IN `0x81`, informes de 8 bytes y
salida por SET_REPORT tipo Output / ID 0. Cada escritura hidraw lleva un byte de ID cero
delante de los 8 bytes de datos. No se desacopla el controlador del kernel. Se verifican
VID:PID mediante sysfs y la ruta seleccionada antes de transmitir. Un bloqueo cooperativo
no impide que otro programa que lo ignore use el mismo USB.

QPIGS exige 24 campos y CRC correcto. QPIWS exige las 36 posiciones binarias capturadas;
las posiciones ambiguas no se interpretan. Si QPIGS falla, sus entidades quedan no
disponibles; los fallos de consultas opcionales solo afectan a las entidades dependientes.
PV2 desconocido no se presenta como potencia cero. Descarga diagnósticos desde el
dispositivo para ver el estado de las consultas y las últimas tramas validadas.
