Feature: Patient registration
  As a receptionist
  I want to register a new patient
  So that their details are stored in the system

  Scenario: Register a new patient successfully
    Given the clinic portal API is running
    When I register a patient with all required fields
    Then the patient is registered with a generated patient ID
    And I receive a 201 response

  Scenario: Reject registration with a missing required field
    Given the clinic portal API is running
    When I register a patient without a full name
    Then I receive a 422 response

  Scenario: Search for a patient by name
    Given the clinic portal API is running
    And a patient named "Jane Tan" is already registered
    When I search for patients by the name "Jane"
    Then the search results include "Jane Tan"

  Scenario: Update a patient's contact details
    Given the clinic portal API is running
    And a patient named "Jane Tan" is already registered
    When I update that patient's phone number to "019-1112222"
    Then the patient's phone number is updated to "019-1112222"
