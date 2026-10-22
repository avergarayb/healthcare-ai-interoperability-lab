FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
COPY src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/mini-lis-service-0.0.1-SNAPSHOT.jar /app/mini-lis-service.jar
EXPOSE 8096
ENTRYPOINT ["java", "-jar", "/app/mini-lis-service.jar"]
