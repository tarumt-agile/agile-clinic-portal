Feature: Appointment activity reporting
  As an administrator
  I want date-filtered appointment reports
  So that clinic activity can be analysed and shared

  Scenario: View the current week's daily appointment totals
    Given an administrator is signed in for reporting
    When I request the default appointment activity report
    Then the report contains every day in the current week

  Scenario: Filter appointment activity by a custom date range
    Given an administrator is signed in for reporting
    When I request appointment activity for a custom date range
    Then the report uses the selected custom date range

  Scenario: Export appointment activity as PDF
    Given an administrator is signed in for reporting
    When I export appointment activity for a custom date range
    Then a downloadable PDF report is returned
