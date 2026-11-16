@offline @synthetic
Feature: Research tooling preserves honest evidence
  Offline checks validate authored data and never claim DayZ behavior.

  @AC-003 @CE-011
  Scenario: Reject invalid CE data and report raw coverage
    Given synthetic mission XML with known raw points and invalid variants
    When the CE audit behavior tests execute
    Then invalid data is rejected and coverage remains an offline structural claim

  @AC-009
  Scenario: Reject incomplete or incomparable benchmark evidence
    Given synthetic repeated baseline and candidate CSV measurements
    When the benchmark behavior tests execute
    Then comparison requires matching context and an explicit calibrated budget

  @AC-010 @NET-006
  Scenario: Reject unsupported capability promotions
    Given synthetic capability manifests and hashed artifact files
    When the evidence behavior tests execute
    Then missing runtime proof and tampered artifacts prevent promotion

  @AC-001
  Scenario: Reject dropped requirements and cyclic tasks
    Given authored requirement mappings and task dependencies
    When the project contract behavior tests execute
    Then unmapped obligations and dependency cycles fail admission
