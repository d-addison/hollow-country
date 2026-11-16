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

  @AC-011
  Scenario: Admit bounded operator settings before native execution
    Given authored settings with default-off features and bounded work limits
    When the runtime settings admission tests execute
    Then malformed flags limits and feature dependencies fail admission without engine claims

  @AC-005
  Scenario: Preserve finite interior allocations and depleted search sites
    Given synthetic building identities allocation quotas and reservation states
    When the authored interior policy and source contract tests execute
    Then ambiguous claims cannot refill and server search admission retains every authority gate

  @AC-006
  Scenario: Conserve salvage materials through native recipe definitions
    Given three authored salvage definitions and synthetic material ledgers
    When the crafting policy and native source contract tests execute
    Then invalid ingredients and resource gain cycles fail without claiming native transactions

  @AC-007 @AC-008
  Scenario: Bound infected memory alerts and persistent population accounting
    Given synthetic observed clues finite horde reservations and restart states
    When the authored infected scalar policy tests execute
    Then expired clues overload and unsafe replenishment are rejected without AI claims

  @AC-004
  Scenario: Preserve stock economy budgets and exact rollback
    Given synthetic stock mission files and conservative economy profiles
    When the economy generation install and rollback tests execute
    Then drift and unsupported edits are rejected without claiming effective engine merges

  @AC-011
  Scenario: Package only authored content with explicit unsigned status
    Given synthetic addon sources and private handoff inputs
    When the deterministic package and signing command tests execute
    Then unsafe paths tampering and unsupported release promotion fail admission
