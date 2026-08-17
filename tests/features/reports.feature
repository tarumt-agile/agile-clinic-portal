Feature: Clinic activity reporting
  As an administrator
  I want appointment and patient growth reports
  So that clinic activity can be analysed and monitored

  Scenario: View new patient registrations by month
    Given an administrator is signed in for reporting
    When I request monthly patient registrations for a year
    Then the report contains each month and the yearly total

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

  Scenario: Export monthly patient registrations as PDF
    Given an administrator is signed in for reporting
    When I export monthly patient registrations for a year
    Then a downloadable PDF report is returned
