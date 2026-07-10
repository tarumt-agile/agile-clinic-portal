Feature: Appointment booking
  As a receptionist
  I want to create an appointment for a patient
  So that their visit is recorded in the schedule

  Scenario: Book a new appointment successfully
    Given the clinic portal API is running
    And a registered patient and an active doctor
    When I book an appointment for that patient and doctor at a valid slot
    Then the appointment is booked with a generated reference number
    And I receive a 201 response

  Scenario: Prevent double-booking a doctor's slot
    Given the clinic portal API is running
    And a registered patient and an active doctor
    When that doctor already has an appointment at the same date and time
    And I try to book another appointment with that doctor at the same date and time
    Then I receive a 409 response
