# Evidencia de pruebas locales

Fecha de verificación: 30 de septiembre de 2026. Equipo: macOS con Docker Desktop. Comandos ejecutados en la raíz del repositorio.

| Prueba | Resultado observado |
|---|---|
| Dos procesos Python con base y clave de sesión compartidas | 2 pruebas de integración aprobadas; login, crear, leer, actualizar y eliminar entre procesos |
| Docker Compose | app1, app2 y app3 en estado `healthy`; Nginx activo |
| Round Robin, 30 peticiones | app1 10, app2 10, app3 10 |
| Weighted 5:3:2, 100 peticiones | app1 50, app2 30, app3 20 |
| Caída de app2, 20 peticiones | app1 10, app3 10; ninguna petición atendida por app2 |
| Recuperación de app2 | app1 4, app2 4, app3 4 en 12 peticiones |
| Least Connections | Configuración validada con `nginx -t` y recargada |
| IP Hash, 12 peticiones desde un cliente | Las 12 respondieron desde app2 |

Comandos reproducibles:

```bash
python3 -m unittest discover -s tests -v
./scripts/smoke.sh
./scripts/set-algorithm.sh weighted
./scripts/count-distribution.sh 100
./scripts/set-algorithm.sh round_robin
```

Los conteos son evidencia empírica de esta ejecución, no una garantía de idéntico resultado en cualquier escenario. En particular, Least Connections debe probarse con conexiones concurrentes y el comportamiento de failover depende del tiempo configurado y del momento de la solicitud.

## Comparación con Apache Benchmark

Prueba ejecutada con `./scripts/benchmark.sh`: 1000 peticiones, concurrencia 50, endpoint `/api/instance`.

| Destino | Peticiones por segundo | Tiempo por petición | Fallos |
|---|---:|---:|---:|
| app1 directo | 130.76 | 382.393 ms | 0 |
| Nginx → tres backends | 817.42 | 61.168 ms | 0 |

En esta ejecución el balanceador alcanzó 6.25 veces más peticiones por segundo. Nginx repartió la carga entre tres procesos de aplicación; la prueba directa concentró las 50 conexiones en uno. El tiempo medio por petición bajó de 382.393 a 61.168 ms. Ambos recorridos terminaron sin fallos. Estas cifras dependen del equipo, Docker, la red local y el endpoint usado. La respuesta de `/api/instance` es pequeña y no representa una aplicación con consultas costosas. Nginx también añade un salto de proxy, de modo que no siempre reduce la latencia. Para una comparación más completa convendría repetir las mediciones, probar varias concurrencias y observar CPU por contenedor. En este laboratorio la prueba apoya el beneficio de distribuir carga, junto con la evidencia de continuidad durante la caída de app2.

## Evidencia AWS pendiente

La pila AWS se documenta en [aws.md](aws.md). Registrar allí el DNS del ALB, estado saludable de los targets, respuestas de `/` y `/api/test`, capturas de la regla `/api/*` y métricas del Auto Scaling Group una vez desplegado.
