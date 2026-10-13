# Evidencia de prueba.pcapng

Captura leída desde el archivo local indicado por el usuario. Tamaño: 141360 bytes.
SHA-256: `94d0a573168a2839768953962cbeda056fcbf02b6d8f3119bad71866fd4c5091`.
Formato pcapng; interfaz de enlace USBPcap 249. Números de paquete: EPB, desde 1.

## USB observado

- Descriptor de dispositivo, paquete 14: `0665:5161`, bcdDevice `0002`.
- Descriptor de configuración, paquete 16: interfaz 0, clase HID 3, un endpoint
  interrupt IN `0x81`, wMaxPacketSize 8. No hay endpoint interrupt OUT.
- Peticiones Output SET_REPORT: setup `21 09 00 02 00 00 08 00` (8 bytes de datos).
- Respuestas: informes de 8 bytes por `0x81`, sin byte inicial de report ID.
- El descriptor de informes HID no está presente en esta captura; no se afirma
  haberlo validado. La implementación replica el comportamiento de tráfico observado.

En USBPcap las transferencias control de envío tienen los 8 bytes de setup seguidos
de los datos. No se deben interpretar esos bytes de setup como el comando del inversor.
Las lecturas pendientes sin carga útil no son respuestas vacías del inversor.

## Consultas de interés

| Consulta | Petición protocolo sin relleno | Respuestas completas | Incompletas |
|---|---|---:|---:|
| QPIGS | `51 50 49 47 53 b7 a9 0d` | 14 | 1 |
| QPIGS2 | `51 50 49 47 53 32 68 2d 0d` | 7 | 0 |
| QMOD | `51 4d 4f 44 49 c1 0d` | 8 | 0 |

QPIGS2 requiere dos informes de salida, el segundo `0d 00 00 00 00 00 00 00`.
QMOD ocupa un informe, con un cero final. Las 30 peticiones coinciden byte por byte
con el constructor CRC16-XMODEM (valor inicial 0, polinomio 0x1021, orden alto/bajo,
incremento de bytes CRC 0x28/0x0d/0x0a). Las 29 respuestas completas pasan CRC.
La petición final QPIGS del paquete 2139 tiene una respuesta sin terminador y se rechaza.
La captura empieza con el final de una respuesta cuya petición no está presente;
esa respuesta huérfana no se asigna a una consulta inventada.

Primeros valores observados:

| Consulta / paquete de petición | Resultado |
|---|---|
| QPIGS / 145 | 24 campos; salida AC 2696 W, batería 55.80 V / 2 A carga / 76% / 0 A descarga; PV1 7.8 A / 181.0 V / 1427 W |
| QPIGS2 / 179 | `03.4 376.8 01290 ` → PV2 3.4 A / 376.8 V / 1290 W |
| QMOD / 141 | B (modo batería) |

La respuesta QPIGS2 tiene un espacio antes del CRC: ese espacio **participa en el CRC**.
Solo se divide el texto en campos después de validar los bytes originales.
El relleno cero después de CR se admite; datos no nulos después de CR se rechazan.

## Significado de los campos

Se contrastó el documento del fabricante
[Axpert MAXII, VMIV, MKSIV Communication Protocol20221104-Twin.doc](https://ftps.voltronic.com.tw/E/Easunpower-93CB312922AC474787C6/RS232%20%E9%80%9A%E8%A8%8A%E5%8D%94%E8%AD%B0%28communication%20protocol%29/Axpert%20MAXII%2CVMIV%2C%20MKSIV%20Communication%20Protocol20221104-Twin.doc),
secciones 2.9, 2.10 y 2.12. Los campos expuestos coinciden con el orden documentado
y con el formato capturado. El documento incluye un campo final reservado de corriente
de red que no aparece en el perfil de 24 campos observado: no se expone ni se rellena.
No se incluye el documento completo en este repositorio.

Esto confirma la estructura del protocolo y el significado documentado; no valida la
precisión física de cada sensor. Todos los datos observados pertenecen a un único equipo
y período de captura. No demuestra operación bajo todos los modos, batería real/BMS,
doble salida AC ni todos los firmwares.
