package lab.healthcare.minilis;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

@RestControllerAdvice
class MiniLisExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(MiniLisExceptionHandler.class);

    @ExceptionHandler(MiniLisException.class)
    ResponseEntity<Map<String, String>> domain(MiniLisException ex) {
        log.info("mini_lis_rejected error={}", ex.code());
        return ResponseEntity.status(ex.httpStatus()).body(Map.of("error", ex.code()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<Map<String, String>> invalid(MethodArgumentNotValidException ex) {
        log.info("mini_lis_rejected error=invalid_request");
        return ResponseEntity.badRequest().body(Map.of("error", "invalid_request"));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    ResponseEntity<Map<String, String>> unreadable(HttpMessageNotReadableException ex) {
        log.info("mini_lis_rejected error=invalid_request");
        return ResponseEntity.badRequest().body(Map.of("error", "invalid_request"));
    }
}
