FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY services/mini-his-simulator /src/mini-his-simulator
COPY services/mini-lis-service /src/mini-lis-service
COPY services/fhir-integration-service /src/fhir-integration-service
RUN mvn -q -DskipTests -f /src/mini-his-simulator/pom.xml install \
 && mvn -q -DskipTests -f /src/mini-lis-service/pom.xml install \
 && mvn -q -DskipTests -f /src/fhir-integration-service/pom.xml package

FROM eclipse-temurin:21-jre
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /src/fhir-integration-service/target/fhir-integration-service-0.0.1-SNAPSHOT.jar /app/fhir-integration-service.jar
COPY services/fhir-integration-service/docker/entrypoint.sh /opt/platform/entrypoint.sh
RUN chmod +x /opt/platform/entrypoint.sh
EXPOSE 8081
ENTRYPOINT ["/opt/platform/entrypoint.sh"]
