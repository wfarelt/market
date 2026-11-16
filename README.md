# market

## Fecha de trabajo

La configuración de fecha de trabajo global está en preparación. Por ahora la
aplicación funciona en modo automático y utiliza la fecha local actual. El modo
histórico permanece bloqueado hasta integrar y validar todos los módulos
operativos y reportes; no debe habilitarse modificando directamente la base de
datos. Los cambios de configuración quedan registrados con el usuario y el
momento real.

Las operaciones que dependen de la fecha de trabajo y sus cambios se
coordinan dentro de transacciones. Si SQLite no puede obtener el bloqueo, la
operación se rechaza y debe intentarse nuevamente.

Las nuevas cajas guardan la fecha de trabajo al abrirse y conservan la fecha y
hora reales de apertura y cierre. Las cajas anteriores a esta actualización
mantienen su fecha de negocio como no determinada; no se infiere de sus ventas.
El criterio anterior del reporte filtra las cajas por la fecha real de cierre.
En modo histórico los gastos requieren que la fecha de negocio de la caja
coincida con la fecha de trabajo. Una caja con fecha desconocida o distinta se
puede cerrar sin asignarle una fecha nueva.
En el administrador de Django las cajas, movimientos, gastos y rectificaciones
son de solo consulta; las operaciones se realizan en las pantallas de caja.
Las existencias y los movimientos de inventario también son de solo consulta
en el administrador; se gestionan desde las pantallas de inventario.
Las ventas y sus líneas son de solo consulta en el administrador y se
gestionan desde el punto de venta.
Las compras y sus líneas son de solo consulta en el administrador; los
proveedores siguen siendo editables.
Los traspasos y sus líneas son de solo consulta en el administrador y se
procesan desde las pantallas de traspasos.
Las ventas registran la fecha de negocio y el momento real de confirmación por
separado. En ventas anteriores, la fecha de negocio procede de la fecha de
venta registrada; la confirmación real no se conoce. En modo automático se
mantiene la selección de fecha existente y los reportes conservan sus filtros
anteriores. El modo histórico aún no está disponible.

El resumen de reportes permite elegir el criterio anterior, fecha de negocio o
fecha real. Por defecto conserva el criterio anterior en modo automático. Los
registros sin fecha para el criterio elegido se muestran como omitidos sin
atribuirlos a un periodo. En el criterio de fecha de negocio, los créditos se
filtran por la fecha de su venta y los cobros por su propia fecha de negocio.
En los criterios anterior y real se usa la fecha real de registro de ambos; el
inventario y los saldos de crédito son siempre valores actuales.
Los cobros nuevos guardan la fecha de negocio de su caja y su fecha real de
registro; los cobros anteriores conservan la fecha de negocio no determinada.
La fecha de negocio de un crédito corresponde a la fecha de su venta.
El listado de ventas conserva la fecha de venta registrada en modo automático.
En modo histórico filtra por fecha de negocio y avisa si hay ventas sin esa
fecha que cumplen los demás filtros y permisos.
Durante la carga histórica, el precio unitario de una línea en borrador puede
ajustarse para esa venta sin modificar el precio del catálogo.
El dashboard usa la fecha de negocio de la fecha de trabajo para el indicador
de ventas del usuario en modo histórico; las ventas recientes abarcan todas las
fechas y las existencias y traspasos pendientes muestran su estado actual.

Las compras confirmadas registran por separado la fecha de negocio y el momento
real de confirmación. Las compras anteriores mantienen su fecha de negocio como
no determinada. El criterio anterior de reportes de compras utiliza la fecha
real de confirmación.

Los movimientos de inventario nuevos registran su momento real de confirmación;
para los anteriores no está disponible. En modo histórico, la fecha del movimiento debe coincidir con la
fecha de trabajo. El modo automático conserva la fecha editable.
Una existencia inicial nueva mayor que cero genera una entrada confirmada en el
kardex; una existencia inicial de cero no genera movimiento. No se crean
movimientos retroactivos para existencias ya registradas.

Los traspasos nuevos registran la fecha de negocio del envío y los momentos
reales de envío y recepción. En modo histórico, el envío y la recepción usan la
misma fecha de trabajo. Los traspasos anteriores mantienen su fecha de negocio
como no determinada.
Para entrar al modo histórico deben recibirse todos los traspasos pendientes.
Si el sistema ya está en modo histórico y solo quedan traspasos pendientes
antiguos sin fecha de negocio, cierre todas las cajas y vuelva a modo automático
para recibirlos. La fecha original del envío permanece sin determinar. Si hay
traspasos pendientes con fecha, deben recibirse primero en su fecha histórica.

## Preparación de despliegue de la fecha de trabajo

Este procedimiento requiere una ventana de mantenimiento y autorización del
responsable. **No habilita el modo histórico** ni sustituye la validación en el
entorno del cliente. El código y las migraciones deben distribuirse juntos;
esta versión no debe atender solicitudes contra una base sin migrar.

### Antes de intervenir

1. Identificar la instalación, versión vigente, servicio, entorno virtual,
   configuración efectiva y ruta real de la base. Las configuraciones incluidas
   usan SQLite en `BASE_DIR / db.sqlite3`; una instalación puede diferir.
   Verificar también el directorio de archivos subidos (`MEDIA_ROOT`) y el
   almacenamiento disponible. No asumir que una copia local corresponde al
   cliente.
2. Reservar la ventana, impedir el acceso y detener **todos** los procesos que
   leen o escriben en la base y los archivos subidos, incluidas tareas
   programadas. Mantenerlos detenidos hasta finalizar o restaurar. Registrar
   cantidades y totales relevantes por sucursal, cajas abiertas y traspasos
   enviados para comparar después. No cerrar ni recibir operaciones sin la
   participación del cliente.
3. Guardar una copia íntegra de la versión anterior de la aplicación y sus
   dependencias, configuración y archivos subidos, con acceso restringido.
   La configuración puede contener secretos: no incluirla en Git ni compartirla
   por canales no autorizados.
4. Crear un respaldo consistente de SQLite con la API `backup`, en una ruta
   nueva, protegida y distinta de la base original. Por ejemplo, con el Python
   de la instalación y las rutas absolutas correctas sustituidas previamente:

   ```sh
   umask 077
   /ruta/al/venv/bin/python - /ruta/real/db.sqlite3 /ruta/segura/respaldo.sqlite3 <<'PY'
   import sqlite3
   import sys
   from pathlib import Path

   source = Path(sys.argv[1]).resolve(strict=True)
   target = Path(sys.argv[2]).absolute()
   with target.open("xb"):
       pass
   with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
       with sqlite3.connect(target) as dst:
           src.backup(dst)
           result = dst.execute("PRAGMA integrity_check").fetchall()
           if result != [("ok",)]:
               raise RuntimeError(f"El respaldo no pasó integrity_check: {result}")
   print("Respaldo verificado:", target)
   PY
   ```

   Si falla, detener el procedimiento y no utilizar el archivo incompleto.
   Conservar el respaldo fuera de la instalación, con permisos restringidos y
   según la política de retención del cliente. Verificar que se pueda restaurar
   en una ubicación aislada; una comprobación de integridad no reemplaza esa
   prueba.

### Ensayo aislado

1. Preparar una instalación separada de la versión nueva, inaccesible a los
   usuarios y procesos de producción, con su propia configuración, dependencias
   y directorio de archivos subidos. Copiar allí el respaldo y los archivos
   necesarios; no apuntar a la base ni al almacenamiento productivos.
2. Confirmar expresamente la ruta efectiva de `DATABASES["default"]["NAME"]`
   y `MEDIA_ROOT` en esa instalación. Con el entorno adecuado y desde su raíz,
   ejecutar `python manage.py showmigrations`, `python manage.py migrate --plan`,
   `python manage.py migrate --noinput`, `python manage.py check` y
   `python manage.py showmigrations`. Investigar cualquier error antes de seguir.
   No usar `--fake` para eludir errores.
3. Comparar los registros y totales anotados con el estado migrado. Verificar
   que la fecha de trabajo esté en automático, el histórico siga bloqueado y
   que cajas y traspasos pendientes sigan presentes. Comprobar ventas, compras,
   inventario, créditos y reportes en la copia, incluyendo las advertencias de
   fechas desconocidas. No registrar operaciones de prueba en producción.
4. La migración de ventas deriva su fecha de negocio de `completed_at` en la
   zona horaria configurada, sin inventar su confirmación real. Cajas, compras,
   cobros y traspasos anteriores pueden no tener fecha de negocio; movimientos
   anteriores pueden no tener confirmación real. Confirmar que estas ausencias
   sean aceptables y que el criterio anterior de los reportes conserve los
   totales esperados.

### Instalación y recuperación

Solo después de un ensayo satisfactorio y aprobación explícita para la
intervención: repetir el respaldo inmediatamente antes del cambio, mantener la
ventana de mantenimiento, instalar exactamente la versión ensayada y ejecutar
el plan y las migraciones en la base confirmada. Revisar `showmigrations`,
`check`, integridad de SQLite y las mismas comparaciones antes de reabrir el
servicio. Resolver con el cliente los traspasos pendientes antes de intentar
activar histórico. La habilitación requiere una aprobación separada.

Si hay un fallo, no reabrir el servicio. Con autorización, restaurar juntos la
versión anterior, su configuración, archivos subidos y la base del respaldo
verificado; antes preservar la instalación fallida para diagnóstico. Asegurar
que ningún proceso use SQLite y tratar los archivos auxiliares WAL/SHM de forma
coherente con la restauración, sin mezclarlos con la base restaurada. Restaurar
el respaldo descarta cualquier operación posterior a su captura: coordinarlo
con el cliente. Comprobar integridad y funcionamiento antes de reabrir.
shop
