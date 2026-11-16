@manual @runtime @pending
Feature: Hollow Country runtime acceptance
  These are manual protocols, not executable offline acceptance.

  @AC-002
  Scenario: Local official server loads the signed smoke mod
    Given matching installed DayZ client and dedicated server builds
    And a diagnostic hello-world and officially built signed PBO
    When a normal client joins and reconnects after server restart
    Then the smoke event and persistence checks have captured logs and hashes

  @AC-004 @CE-003 @CE-004
  Scenario: Apartment and barracks have real eligible opportunities
    Given verified building classnames and vanilla CE control fixtures
    When the minimal native economy change runs in the same controlled mission
    Then valid accessible placements are observed without CE errors or inflation

  @AC-005 @INT-007 @NET-002
  Scenario: Two clients race to claim a persistent search site
    Given a server allocated site and two eligible clients
    When both search concurrently and retry across a server restart
    Then exactly one allocation commits and the site stays depleted

  @AC-006 @CRF-004 @CRF-005
  Scenario: Interrupted salvage does not create free materials
    Given a verified native recipe and server owned inputs
    When clients race or disconnect and the inventory is full
    Then outputs and consumed inputs recover as a single valid transaction

  @AC-007 @AI-004 @AI-006 @AUD-004
  Scenario: A player can escape an audible searcher
    Given two observing clients and a native navigation and audio control
    When the player breaks sight quietly and changes location
    Then the searcher follows observed clues and expires its memory
    And locomotion stays physically audible without hidden live tracking

  @AC-008 @HOR-002 @HOR-006 @HOR-009 @HOR-010
  Scenario: Hordes and local chains coexist without visible materialization
    Given a persistent horde and finite shared infected and alert budgets
    When a real audible chain attracts the group across two observers and restart
    Then population and identity reconcile without doubling or visible pop-in

  @AC-009 @AC-011
  Scenario: The private transfer is reversible at the intended co-op load
    Given calibrated repeated 3 to 6 player benchmarks and a signed package
    When the friend installs on a matching server and restores a save backup
    Then module combinations and rollback preserve state within approved budgets
