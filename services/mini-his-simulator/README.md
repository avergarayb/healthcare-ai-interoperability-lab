# Mini HIS Simulator

Servicio de laboratorio independiente. Escucha solo en `127.0.0.1:8095` y usa su propio SQLite. No llama a Java, Python ni HAPI.

Desde la raíz del repositorio:

```text
mvn -f services/mini-his-simulator/pom.xml spring-boot:run
```

Consultas:

```text
GET  http://127.0.0.1:8095/health
GET  http://127.0.0.1:8095/patients
GET  http://127.0.0.1:8095/patients/MHS-PAT-001
GET  http://127.0.0.1:8095/patients/MHS-PAT-001/consultations
GET  http://127.0.0.1:8095/consultations/MHS-CON-001
GET  http://127.0.0.1:8095/consultations/MHS-CON-001/results
GET  http://127.0.0.1:8095/patients/MHS-PAT-001/results
POST http://127.0.0.1:8095/synthetic/reset
```

Los listados aceptan `limit` (predeterminado 50, máximo 100). `POST /synthetic/reset` solo responde si el llamador es loopback.
