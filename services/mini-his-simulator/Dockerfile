FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
COPY src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/mini-his-simulator-0.0.1-SNAPSHOT-exec.jar /app/mini-his-simulator.jar
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 0555 /entrypoint.sh && mkdir -p /app/data
EXPOSE 8095
ENTRYPOINT ["/entrypoint.sh"]
