package lab.healthcare.fhir;

import lab.healthcare.fhir.config.LocalDotEnv;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class FhirIntegrationServiceApplication {

    public static void main(String[] args) {
        LocalDotEnv.loadIfPresent();
        SpringApplication.run(FhirIntegrationServiceApplication.class, args);
    }
}
