# Mini LIS

Servicio de laboratorio independiente. Representa la organización `org-mini-lis`, distinta del Mini HIS. Escucha en `127.0.0.1:8096` salvo que un contenedor habilite otro bind, y usa su propio PostgreSQL. No llama a Java, Python, HAPI ni al Mini HIS.

PostgreSQL local, sin tocar la base de HAPI:

```text
docker compose -f infra/docker/docker-compose.yml up -d mini-lis-postgres
```

El puerto publicado es `5433`. Luego, desde la raíz del repositorio:

```text
mvn -f services/mini-lis-service/pom.xml spring-boot:run
```

La API clínica exige `X-Service-Token`. El valor de laboratorio es `lab-mini-lis-dev`. `/health` no lo exige.

```text
GET  http://127.0.0.1:8096/health
GET  http://127.0.0.1:8096/patients/MLS-PAT-001
GET  http://127.0.0.1:8096/orders/MLS-ORD-001
GET  http://127.0.0.1:8096/orders/MLS-ORD-002/results
GET  http://127.0.0.1:8096/patients/MLS-PAT-003/results
```

Para leer esos datos como FHIR R4 hay que arrancar FHIR Integration Service con `--clinical-read.source=mini-lis`. El valor por defecto sigue siendo `local-hapi`. Python y LangGraph no cambian de origen por este servicio.

El contenedor completo, aplicación incluida, es:

```text
docker compose -f infra/docker/docker-compose.yml up -d --build mini-lis
```

Ese modo publica `8096` y pone `MINI_LIS_ALLOW_EXTERNAL_BIND=true` dentro del contenedor. La base queda en el volumen `mini-lis-postgres-data`.
