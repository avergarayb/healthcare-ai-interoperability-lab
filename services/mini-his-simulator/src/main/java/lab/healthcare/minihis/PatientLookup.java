package lab.healthcare.minihis;

import java.util.List;

public record PatientLookup(List<PatientView> patients, boolean truncated) {
}
