package lab.healthcare.minihis;

public record AppointmentView(
        String appointmentId,
        String patientId,
        String status,
        String start) {
}
