# ha-axpert-max-twin

Integración personalizada de Home Assistant para el perfil USB HID capturado en un
Axpert MAX TWIN 11 kW. Compatible con repositorios personalizados de HACS. Solo consulta
el inversor: **QPIGS, QPIGS2, QMOD y QPIWS**. No incorpora controles ni comandos arbitrarios.

## Versiones

- **0.2.0:** 33 entidades: nuevos campos AC/red/temperatura, cálculos, alarmas y energía
  estimada total, diaria, mensual y anual. [Detalle y límites](docs/v0.2.0.md).
- **0.1.1:** respaldo con las 12 entidades originales y el intervalo configurable desde
  5 segundos. [Recuperar respaldo](https://github.com/Depintopinto/ha-axpert-max-twin/releases/tag/v0.1.1).

La ampliación se comprueba offline con 40 respuestas completas capturadas y pruebas
en Home Assistant, incluida Core 2026.9.4. La comunicación de 0.1.1 funcionó físicamente
en el equipo del usuario; QPIWS y los contadores nuevos quedan pendientes de prueba
física después de actualizar. No se declara compatibilidad con otros firmwares por
compartir nombre MAX/TWIN o VID:PID.

## Instalación y actualización

1. Detén WatchPower, `axpert_inverter`, mppsolar y otros clientes del mismo USB.
2. En HACS → Repositorios personalizados, añade
   `https://github.com/Depintopinto/ha-axpert-max-twin`, categoría **Integración**.
3. **Descarga** la integración: añadir el repositorio no instala sus archivos.
4. Reinicia Home Assistant completo y añade **Axpert MAX TWIN** en Dispositivos y servicios.
5. Selecciona el `/dev/hidrawN` del inversor. Intervalo predeterminado: **5 segundos**.

La actualización conserva el dispositivo, los identificadores de las 12 entidades
originales y el intervalo guardado. En **Configurar** puedes cambiarlo entre 5 y 3600
segundos; se recarga automáticamente. Actualizar archivos sí necesita reiniciar Core.

Instalación manual: copia `custom_components/axpert_max_twin` a
`/config/custom_components/axpert_max_twin` y reinicia. No necesita dependencias USB
binarias, MQTT ni un add-on adicional. Requiere Linux con hidraw; mínimo declarado de
Core 2026.1. Está preparado para HA OS aarch64, con acceso USB dentro de Core.

### Si no aparece en «Añadir integración»

Confirma que HACS descargó **Depintopinto/ha-axpert-max-twin** y que existen
`/config/custom_components/axpert_max_twin/manifest.json` y `config_flow.py`.
`ArnyminerZ/ha-axpert-inverter` es otra integración. Tras reiniciar, prueba Ctrl+F5 o
[el formulario directo](https://my.home-assistant.io/redirect/config_flow_start/?domain=axpert_max_twin).
Busca en los registros `axpert_max_twin`, `homeassistant.loader` o `config_flow`.
Los errores de ESPHome o `axpert_inverter` no diagnostican esta integración.

## Sensores por grupo

| Grupo lógico | Entidades | Contenido |
|---|---:|---|
| Consumo / salida AC | 11 | V, Hz, VA, W, carga %, corriente calculada, factor de potencia y 4 contadores kWh estimados |
| Solar | 11 | Los 6 sensores PV1/PV2, potencia total calculada y 4 contadores kWh estimados |
| Estado del inversor | 11 | Red V/Hz, batería, temperatura del disipador, modo original y traducido, alarmas y trama de diagnóstico |

Los nombres y el atributo `sensor_group` permiten distinguir los grupos, manteniendo
un único dispositivo. La trama original QPIWS es una entidad de diagnóstico deshabilitada
por defecto; puedes habilitarla en el registro de entidades. Los campos nuevos y los
estados de modo/alarma tienen traducciones al español y al inglés.

Los kWh son **estimaciones** de la integral temporal de potencia, con persistencia y
acumulados según la zona horaria de HA. No se importan datos históricos ni se rellenan
desconexiones. Se guardan cada 60 segundos, al descargar la integración y al apagar HA de forma normal; un corte
abrupto puede perder la fracción aún no guardada. Para Energía elige los contadores
totales de salida AC y solar, no los del día/mes/año.
Consulta [metodología, campos exactos y límites](docs/v0.2.0.md).

El consumo es la salida AC comunicada por el inversor: no separa sus dos salidas ni
consumos externos de la vivienda. El % de batería procede del inversor, no de un BMS
independiente. Las potencias PV son las potencias de carga comunicadas. La corriente
y el factor de potencia calculados no se presentan como mediciones directas.

## USB y diagnósticos

Perfil observado: `0665:5161`, interfaz 0, interrupt IN `0x81`, informes de 8 bytes y
salida por SET_REPORT tipo Output / ID 0. Cada escritura hidraw lleva un byte de ID cero
delante de los 8 bytes de datos. No se desacopla el controlador del kernel. Se verifican
VID:PID mediante sysfs y la ruta seleccionada antes de transmitir. El bloqueo cooperativo
no impide que otro programa que lo ignore use el mismo USB.

QPIGS exige 24 campos y CRC correcto. QPIWS exige las 36 posiciones binarias capturadas;
las posiciones finales ambiguas no se interpretan como códigos de fallo. Un fallo de
QPIGS deja las entidades no disponibles; los fallos opcionales solo afectan a entidades
dependientes. PV2 desconocido no se convierte en potencia cero.

Descarga diagnósticos desde el dispositivo: incluyen estado de las cuatro consultas y
sus últimas tramas validadas, sin número de serie ni rutas de configuración. Que un
terminal add-on vea el USB no demuestra acceso desde Core. Los nombres hidraw pueden
cambiar tras una reconexión.

## Pruebas y análisis

```sh
python -m unittest discover -s tests -v
python -m compileall -q custom_components tools
# En Linux con el Python requerido por Home Assistant:
pip install 'homeassistant==2026.9.4'
python -m unittest discover -s tests_ha -v
```

Las pruebas cubren informes reales, CRC, comandos prohibidos, desconexiones, consultas
opcionales, fórmulas, persistencia, cortes de lectura, límites de día/mes/año y horario
de verano. CI comprueba Core 2026.9.4 y la versión disponible. Los fallos QPIWS modificados
en las pruebas son sintéticos, no observados en la captura.

```sh
python tools/analyze_capture.py /ruta/prueba.pcapng informe.json
```

El analizador es offline para USBPcap/pcapng EPB (enlace 249). Su informe completo puede
contener identificadores: revísalo antes de compartirlo. El repositorio solo incluye
las cuatro consultas permitidas, sin captura original ni números de serie.
Ver [captura](docs/capture-analysis.md), [fallo original](docs/upstream-analysis.md) y
[versión nueva](docs/v0.2.0.md).
