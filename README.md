# ViciCampaignCloner

Clonación controlada de la campaña **WD** desde Aliados hacia CentrosMED.

## Alcance
- Campaña `WD` en `vicidial_campaigns`, inicialmente `active=N`.
- Grupo `CC-MED-WD` en `vicidial_user_groups`.
- Agentes `AGENTE-WD_01` a `AGENTE-WD_15` y supervisor `Sup_WD_1`, preservando su contraseña de acceso y permisos compatibles.
- No copiar listas, leads, historial, teléfonos ni credenciales SIP. `phone_login` y `phone_pass` se dejan vacíos, incluso para el supervisor.
- Nunca almacenar contraseñas o exportaciones SQL con secretos en Git.

## Requisitos
Python 3.6+ y PyMySQL; dos conexiones MariaDB mediante transporte protegido (VPN/túnel SSH o TLS). Credenciales mediante variables de entorno privadas. El origen debe usar cuenta de solo lectura.

## Uso
```bash
python3 -m pip install -r requirements.txt
export SOURCE_HOST=127.0.0.1 SOURCE_PORT=13306 SOURCE_USER=lectura_aliados
export TARGET_HOST=127.0.0.1 TARGET_PORT=23306 TARGET_USER=clonador_centrosmed
# Introducir SOURCE_PASSWORD y TARGET_PASSWORD solo mediante un almacén seguro
python3 cloner.py plan
```

`plan` comprueba existencia, conflictos y esquemas sin escribir. `apply` está deshabilitado hasta asegurar respaldo recuperable, conexiones protegidas y revisión del plan. No ejecutar clonación en producción sin esa validación.

## Riesgos operativos
La tabla `vicidial_campaigns` de CentrosMED usa MyISAM: no existe reversión transaccional fiable. El prefijo `6602`, el grupo y la lista manual `998` requieren validación independiente; la lista pertenece a `TESTCAMP` en destino y **no** debe reasignarse.

No se implementan extensiones SIP, despliegue web ni cambios en Asterisk en esta fase.
