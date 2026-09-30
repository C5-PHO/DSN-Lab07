# Guion de grabación Lab07

El video muestra dos partes: la aplicación funcional con Nginx en Docker y el ALB en AWS. Se recomienda comenzar a grabar **después** de que la pila AWS esté `CREATE_COMPLETE` y los targets aparezcan `healthy`, para no incluir tiempos de espera. La grabación puede ser sin audio; mantener cada resultado visible unos segundos.

## Preparación de ventanas

Abrir antes de grabar:

1. Aplicación local: `http://127.0.0.1:8080`.
2. GitHub: `https://github.com/C5-PHO/DSN-Lab07`.
3. Terminal en `/Users/piero/Desktop/DSN/Lab07`.
4. AWS CloudFormation, EC2 Target Groups, Load Balancers y Auto Scaling Groups en `us-east-1`.

Evitar mostrar contraseñas, tokens, datos de facturación o claves. El video solo necesita la evidencia técnica.

## Recorrido sugerido de 7 a 10 minutos

| Orden | Mostrar en pantalla | Evidencia visible |
|---:|---|---|
| 1 | README en GitHub, arquitectura y lista de commits | Código y diseño reproducibles |
| 2 | Login local y lista de artículos | Autenticación y servidor que atendió |
| 3 | Crear, actualizar y eliminar un artículo | CRUD; refrescar entre acciones y ver que cambia `app1/app2/app3` sin perder sesión ni datos |
| 4 | Terminal: `./scripts/count-distribution.sh 30` | Round Robin 10/10/10 aproximadamente |
| 5 | `./scripts/set-algorithm.sh weighted` y `./scripts/count-distribution.sh 100` | Proporción 5:3:2; restaurar `round_robin` después |
| 6 | `docker compose stop app2`, contar 20 solicitudes y `docker compose start app2` | Disponibilidad durante la caída y recuperación |
| 7 | AWS Target Groups y DNS del ALB en navegador | Dos targets web y uno API saludables; `/` alterna instancias |
| 8 | AWS listener y `http://DNS-ALB/api/test` | Regla `/api/*` dirige al backend API |
| 9 | AWS Auto Scaling Group y política de CPU | Mínimo 2, deseado 2, máximo 4; target tracking al 50% |
| 10 | `docs/evidence.md` y resumen final | Pruebas de carga, salud y resultados |

Si no se observa escalado real, mostrar la política configurada y las métricas disponibles; no afirmar un aumento de instancias no observado. Una página estática puede no generar suficiente CPU para activar el escalado.

## Después de guardar el video

Avisar que la grabación quedó guardada. Eliminar la pila `lab07-alb` de CloudFormation y esperar `DELETE_COMPLETE`; verificar que no quede ALB ni EC2 del laboratorio. El código, la plantilla y el video conservan la evidencia y permiten recrear el entorno más adelante sin cargos continuos.
