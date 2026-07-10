Feature: Medical record documentation
  As a doctor
  I want to document a consultation and its diagnosis
  So that the visit is captured in the patient's medical history

  Scenario: Document a consultation with a diagnosis
    Given the clinic portal API is running
    And a registered patient and an active doctor
    When I document a consultation with a diagnosis for that patient and doctor
    Then the consultation note is saved with a generated record number
    And I receive a 201 response

  Scenario: Reject a consultation note with no diagnosis
    Given the clinic portal API is running
    And a registered patient and an active doctor
    When I try to document a consultation with no diagnosis
    Then I receive a 422 response
