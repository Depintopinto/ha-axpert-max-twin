# ha-axpert-max-twin

Integración personalizada de Home Assistant, de **solo lectura**, para el perfil USB
HID observado en un Axpert MAX TWIN 11 kW con WatchPower. Se instala como repositorio
personalizado de HACS. Versión experimental `0.1.0`.

**Verificado:** reproducción offline de 29 respuestas completas de `prueba.pcapng`,
CRC de las peticiones y respuestas, fragmentación de 8 bytes y sensores indicados
abajo. **Pendiente:** conexión física desde Raspberry Pi 4 / HA OS aarch64, permisos
del contenedor Core y funcionamiento con otros firmwares. No se declara compatibilidad
con todos los MAX, MAX II o TWIN por compartir nombre o VID:PID.

## Instalación con HACS

1. Detén WatchPower, la integración `axpert_inverter`, mppsolar y cualquier otro cliente
   que consulte el mismo USB. El bloqueo es cooperativo y no impide que otro programa
   que ignore el bloqueo use el dispositivo.
2. En HACS, abre **Repositorios personalizados** y añade
   `https://github.com/Depintopinto/ha-axpert-max-twin`, categoría **Integración**.
3. Descarga la integración y reinicia Home Assistant.
4. Añade **Axpert MAX TWIN** en Ajustes → Dispositivos y servicios.
5. Introduce el `/dev/hidrawN` correspondiente al inversor y un intervalo de al menos
   15 segundos (predeterminado 30).

Instalación manual: copia `custom_components/axpert_max_twin` a
`/config/custom_components/axpert_max_twin` y reinicia. No necesita un módulo externo,
MQTT, un add-on ni librerías USB compiladas. Solo usa Python y la interfaz hidraw de
Linux; no desacopla el controlador del kernel. Home Assistant mínimo declarado: 2026.1.
El manifest no instala dependencias. Esto evita una dependencia binaria específica de
arquitectura, pero no sustituye la prueba en aarch64.

## Sensores

| Sensor | Consulta / índice (desde 0) | Unidad |
|---|---|---|
| PV1 input current | QPIGS / 12 | A |
| PV1 input voltage | QPIGS / 13 | V |
| PV1 charging power | QPIGS / 19 | W |
| PV2 input current | QPIGS2 / 0 | A |
| PV2 input voltage | QPIGS2 / 1 | V |
| PV2 charging power | QPIGS2 / 2 | W |
| AC output active power | QPIGS / 5 | W |
| Battery voltage | QPIGS / 8 | V |
| Battery charging current | QPIGS / 9 | A |
| Battery reported capacity | QPIGS / 10 | % |
| Battery discharge current | QPIGS / 15 | A |
| Operating mode code | QMOD | código |

El consumo es la potencia activa de la salida AC comunicada por el inversor;
no equivale necesariamente al consumo total de la vivienda ni separa las dos salidas
TWIN. El porcentaje de batería es el valor informado por el inversor, no una lectura
independiente del BMS. PV1/PV2 son las potencias de carga comunicadas; no se inventa
potencia mediante V×I. No se generan contadores kWh artificiales. Para Energía, usa
la integración Integral de Home Assistant sobre los sensores de potencia, teniendo en
cuenta las interrupciones y el significado de cada medida.

QPIGS debe tener exactamente 24 campos y CRC válido. Un perfil diferente se rechaza
con un error explícito. QPIGS2 y QMOD son consultas opcionales: un fallo hace que sus
sensores queden no disponibles, manteniendo las medidas válidas de QPIGS. Un fallo de
QPIGS deja todas las entidades no disponibles; no presenta datos antiguos como nuevos.

## Diagnóstico y prueba en HA OS

La captura identifica USB `0665:5161`, interfaz 0, entrada interrupt `0x81` y ausencia
de endpoint OUT. La salida se envía por HID `SET_REPORT`, tipo Output, ID 0, con
informes de 8 bytes rellenados con ceros. En Linux cada escritura hidraw incluye además
un byte inicial `0x00` que el kernel consume como report ID: **no es un noveno byte del
protocolo USB**.

La ruta debe existir dentro del entorno de Home Assistant Core, con permiso de lectura
y escritura. Que un terminal add-on vea el USB no demuestra que Core pueda acceder.
La integración también comprueba `HID_ID` en sysfs antes de transmitir. Si falla por
permisos, dispositivo no encontrado o sysfs no accesible, exporta los registros de la
integración y comprueba la exposición del dispositivo; no desactives protecciones
como solución automática. Los nombres `/dev/hidrawN` pueden cambiar después de una
reconexión; vuelve a configurar la ruta si cambia. La selección automática por número
de serie todavía no está implementada.

Descarga los diagnósticos desde la página de la integración. Incluyen estado de cada
consulta y la última trama validada de las tres consultas permitidas. No incluyen
números de serie, ruta de configuración ni texto de excepciones que pueda contener
rutas. Los registros permiten distinguir timeout, respuesta incompleta, CRC incorrecto,
NAK y longitud desconocida. Ningún servicio permite enviar comandos arbitrarios;
no hay selectores, números, interruptores ni comandos que modifiquen el inversor.

Para completar la validación física:

1. Instala en HA OS aarch64 y confirma qué hidraw pertenece a `0665:5161`.
2. Comprueba varias actualizaciones y compara voltajes, potencias y porcentaje con
   la pantalla o con WatchPower usado en otro momento, sin dos clientes simultáneos.
3. Desconecta USB y verifica entidades no disponibles; reconecta y verifica recuperación
   si se conserva la misma ruta.
4. Descarga diagnósticos y registra versiones de Core, HA OS y firmware. No marques
   compatibilidad física confirmada hasta que esta prueba se complete.

## Desarrollo

```sh
python -m unittest discover -s tests -v
python -m compileall -q custom_components tools
# En Linux y en el Python requerido por Home Assistant:
pip install 'homeassistant>=2026.1.0'
python -m unittest discover -s tests_ha -v
```

Las pruebas offline incluyen todas las respuestas QPIGS/QPIGS2/QMOD capturadas,
rechazo de corrupción y tramas truncadas, NAK, comandos prohibidos, timeout,
desconexión, informes fragmentados, escritura parcial y drenaje de datos antiguos.
Las pruebas de Home Assistant usan sus clases reales con USB simulado y se ejecutan
en un trabajo separado de CI. No son pruebas de hardware.

```sh
python tools/analyze_capture.py /ruta/prueba.pcapng informe.json
```

El analizador es offline y admite pcapng con EPB y enlace USBPcap (249). Conserva
el número de paquete y distingue peticiones y completados para no duplicar respuestas.
El informe completo puede contener identificadores de otras consultas: revísalo antes
de compartirlo. El repositorio solo incluye las tres consultas solicitadas, sin la
captura original ni transacciones de número de serie.

Consulta [el análisis de la captura](docs/capture-analysis.md) y
[el análisis del fallo original](docs/upstream-analysis.md).
