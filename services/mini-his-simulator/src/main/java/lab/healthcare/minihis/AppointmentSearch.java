package lab.healthcare.minihis;

import java.util.List;

public record AppointmentSearch(List<AppointmentView> appointments, boolean truncated) {
}
