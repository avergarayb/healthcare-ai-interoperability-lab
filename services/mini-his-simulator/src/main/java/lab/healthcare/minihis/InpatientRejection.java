package lab.healthcare.minihis;

public final class InpatientRejection extends RuntimeException {

    private final String code;
    private final int status;

    public InpatientRejection(String code, int status) {
        super(code);
        this.code = code;
        this.status = status;
    }

    public String code() {
        return code;
    }

    public int status() {
        return status;
    }
}
