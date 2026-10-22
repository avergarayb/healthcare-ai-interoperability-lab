package lab.healthcare.minihis;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

@Component
public class MiniHisSeedLoader implements ApplicationRunner {

    private final MiniHisStore store;

    public MiniHisSeedLoader(MiniHisStore store) {
        this.store = store;
    }

    @Override
    public void run(ApplicationArguments args) {
        store.ensureReady();
    }
}
