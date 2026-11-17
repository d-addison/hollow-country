# Synthetic original packages and opaque save sentinels; no DayZ behavior claim.
Feature: Private portable package transactions preserve runtime profiles

  Scenario: Upgrade activates verified package bytes
    Given an owned synthetic first installation
    When the verified second package is upgraded
    Then the second package bytes are active
    And external runtime profile bytes are unchanged

  Scenario: Targeted rollback is repeatable without undoing another generation
    Given an owned synthetic first installation
    When the verified second package is upgraded
    And its transaction is rolled back twice
    Then the original package bytes are active
    And external runtime profile bytes are unchanged

  Scenario: Uncommitted activation is explicitly aborted
    Given an owned synthetic first installation
    When the upgrade stops after activation
    And recovery explicitly requests abort
    Then the original package bytes are active
    And external runtime profile bytes are unchanged

  Scenario: An already committed upgrade survives an abort recovery request
    Given an owned synthetic first installation
    When the upgrade stops after state commit
    And recovery explicitly requests abort
    Then the second package bytes are active
    And external runtime profile bytes are unchanged
