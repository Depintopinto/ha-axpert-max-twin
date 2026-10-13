# Received empty data from QPIGS

Revisión de [ArnyminerZ/ha-axpert-inverter](https://github.com/ArnyminerZ/ha-axpert-inverter),
commit `6d8991d38e449ba953799d750d9ed5f470c673b0` (manifest 1.0.20).
No se dispone de la versión instalada ni del registro original del fallo en HA.

El texto se lanza en `coordinator.py` cuando `get_general_status()` devuelve `{}`.
Ese método devuelve `{}` para texto vacío, menos de 16 campos y errores de conversión
o índice. Por tanto, el texto no demuestra que el USB haya entregado cero bytes.
Un timeout de `send_command()` en esta versión sigue otra ruta de excepción.

Defectos concretos de `axpert.py`:

1. Comprueba `len(parts) < 16`, pero accede a `parts[16]`: 16 campos provocan IndexError.
2. Si `len(parts) > 16`, accede a `parts[19]`: 17–19 campos provocan IndexError.
3. `read_until()` incluye el relleno después de CR; solo elimina CR cuando es el último
   byte. En la captura hay ceros después de CR. El código intenta recuperarse buscando
   prefijos con CRC válido, pero si no lo logra **acepta igualmente** la división
   estándar con CRC erróneo y decodifica ignorando errores. Puede producir datos
   mal interpretados o un error de conversión que acaba en `{}`.
4. Configura una ruta hidraw, pero el transporte actual la ignora y busca el primer
   `0665:5161` mediante PyUSB. Desacopla el controlador, reclama interfaz y reabre el
   USB por consulta. Los permisos de hidraw no garantizan permisos para ese acceso
   libusb. Además, las lecturas descartan todos los errores USB como si fueran timeout.
5. Divide envíos en grupos de 8 bytes sin rellenar el último. WatchPower usa informes
   fijos de 8 bytes; QPIGS2 necesita un segundo informe con CR y siete ceros. Este
   riesgo no explica por sí mismo un fallo de QPIGS, cuya petición mide exactamente 8.
6. No consulta QPIGS2 y por ello no obtiene PV2 en este perfil.

**Conclusión limitada a la evidencia:** la captura prueba que WatchPower recibe QPIGS
válidos, y permite identificar fallos del analizador y diferencias de transporte.
No demuestra una única causa del error ocurrido en HA. Se reprodujeron las tramas
QPIGS contra el código original del commit revisado, sustituyendo únicamente el
transporte USB por las respuestas capturadas: **14 respuestas completas producen
datos y la respuesta final incompleta produce `{}` por IndexError**, después de
aceptar un CRC incorrecto. Esto reproduce la ruta del mensaje con datos incompletos,
pero no demuestra que esa sea la causa del fallo original. Para atribuir el fallo real hacen
falta versión instalada, excepción anterior al mensaje y bytes recibidos en HA.
La última respuesta cortada de la captura es una prueba de rechazo, no prueba de que
el inversor envíe habitualmente respuestas cortadas.

La nueva implementación elimina esos comportamientos: ruta explícita con VID:PID,
hidraw sin libusb, informes fijos, ensamblado hasta CR, CRC obligatorio, perfil de
longitud explícita, errores diferenciados y solo tres consultas permitidas. El envío
hidraw añade ID cero según la [API oficial del kernel](https://www.kernel.org/doc/html/latest/hid/hidraw.html).
