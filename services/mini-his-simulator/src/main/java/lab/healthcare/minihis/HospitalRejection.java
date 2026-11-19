package lab.healthcare.minihis;

public final class HospitalRejection extends Exception {
    public final int status;
    public final String code;

    HospitalRejection(String code, int status) {
        super(code);
        this.code = code;
        this.status = status;
    }
}
