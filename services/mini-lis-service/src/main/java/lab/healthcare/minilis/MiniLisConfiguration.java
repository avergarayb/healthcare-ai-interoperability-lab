package lab.healthcare.minilis;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;

@Configuration
@EnableConfigurationProperties(Hl7Properties.class)
class MiniLisConfiguration {

    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }
}
