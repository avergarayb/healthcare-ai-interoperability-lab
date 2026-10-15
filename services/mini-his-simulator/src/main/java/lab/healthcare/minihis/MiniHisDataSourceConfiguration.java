package lab.healthcare.minihis;

import org.sqlite.SQLiteConfig;
import org.sqlite.SQLiteDataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.sql.DataSource;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

@Configuration
public class MiniHisDataSourceConfiguration {

    @Bean
    public DataSource miniHisDataSource(@Value("${mini-his.sqlite-path}") String sqlitePath) throws IOException {
        Path file = Path.of(sqlitePath).toAbsolutePath();
        if (file.getParent() != null) {
            Files.createDirectories(file.getParent());
        }
        SQLiteConfig config = new SQLiteConfig();
        config.enforceForeignKeys(true);
        SQLiteDataSource dataSource = new SQLiteDataSource(config);
        dataSource.setUrl("jdbc:sqlite:" + file);
        return dataSource;
    }
}
