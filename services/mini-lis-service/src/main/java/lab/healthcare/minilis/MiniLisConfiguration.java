package lab.healthcare.minilis;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;

@Configuration
class MiniLisConfiguration {

    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }
}
