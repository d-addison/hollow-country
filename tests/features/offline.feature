@offline @synthetic
Feature: Research tooling preserves honest evidence
  Offline checks validate authored data and never claim DayZ behavior.

  @ISSUE-35
  Scenario: Build weather candidates without silently changing native defaults
    Given synthetic native weather XML and explicit pinned operator profiles
    When the bounded atmosphere candidate generator and validator execute
    Then unspecified native settings remain unchanged and no runtime acceptance is inferred

  @ISSUE-56
  Scenario: Retain every audited class in the flashlight candidate denominator
    Given synthetic item metadata with unresolved category and attachment hints
    When the bounded flashlight candidate matrix executes
    Then every class remains counted and geometry power and eligibility remain unqualified

  @ISSUE-52 @ISSUE-56
  Scenario: Bound effective item metadata acquisition without claiming compatibility
    Given synthetic configuration types and explicit export budgets
    When the authored acquisition policies and fixed mission hook checks execute
    Then variants and partial scans remain explicit without geometry or gameplay claims

  @ISSUE-37
  Scenario: Authorize group changes and bound durable server state
    Given synthetic authenticated peers group state and store failures
    When the authored group rules and server orchestration execute
    Then unauthorized changes unsafe persistence and outsider position disclosure fail

  @ISSUE-52 @ISSUE-54
  Scenario: Retain ambiguous recipes in a whole-source census
    Given synthetic source trees with conditional recipes and unregistered descendants
    When the bounded crafting census executes
    Then ambiguous candidates remain unresolved rather than disappearing from coverage

  @ISSUE-53
  Scenario: Reject fuel credits that can create quantity through rounding
    Given synthetic binary32 vehicle and vessel measurements
    When the authored fuel quantum and receipt policies execute
    Then unrepresentable gains fail without claiming a native fluid transaction

  @ISSUE-31
  Scenario: Calculate bounded stamina and carried-load changes
    Given synthetic load exertion recovery and cooldown inputs
    When the authored stamina policy executes
    Then invalid inputs fail and native permission vetoes remain authoritative

  @ISSUE-27
  Scenario: Plan portable criteria without manufacturing acceptance
    Given a bounded acceptance catalog and explicit capability declarations
    When the planning-only adapter executes
    Then criteria stay intact and no execution or PASS is claimed

  @ISSUE-27 @ISSUE-56
  Scenario: Preserve the original and extended ledger without local specs
    Given the portable catalog and unknown capability inventory
    When only those two files are exported for planning
    Then original criteria and fuel and flashlight constraints survive without source documents

  @AC-007
  Scenario: Admit measured room catalogs without enabling production search
    Given synthetic measured room documents and native house collaborators
    When bounded diagnostic catalog admission and binding execute
    Then invalid or ambiguous catalogs publish nothing and production search stays gated

  @AC-008
  Scenario: Veto observer transitions until complete trustworthy evidence exists
    Given synthetic observer samples explicit limits and retained visibility history
    When the authored observer veto and hysteresis policies execute
    Then missing stale visible or unresolved inputs cannot authorize transitions

  @AC-011 @AC-012
  Scenario: Reject unsafe private repository content without echoing secrets
    Given synthetic Git trees private source notices and unsafe content variants
    When bounded repository hygiene admission executes
    Then restricted material and broken links fail without secret excerpts or publication rights

  @AC-004 @AC-005
  Scenario: Prepare interior candidates only from explicit measured evidence
    Given synthetic measured layouts contextual policies and source evidence pins
    When interior candidate preparation and validation execute
    Then unsafe or unproven candidates fail without runtime installation or eligibility claims

  @AC-008
  Scenario: Persist cohort intent before native ownership transfer
    Given synthetic cohort reservations journal generations and crash boundaries
    When the authored durable adoption policies and orchestration execute
    Then uncommitted or ambiguous transfers retain reservations and cannot replay

  @AC-008
  Scenario: Observe route progress and fairly schedule cohort clues
    Given synthetic observed members waypoints and competing cohort clues
    When the authored route progress and retarget scheduler execute
    Then completion requires observed arrival and stale cohorts cannot starve valid clues

  @AC-007 @AC-008
  Scenario: Keep infected profiles and pack retargets bound to observed evidence
    Given synthetic profile assignments member observations and frozen stimuli
    When the authored infected profile and pack routing policies execute
    Then unsupported capabilities stale clues and ambiguous membership remain blocked

  @AC-011
  Scenario: Unwind interrupted module lifecycle without repeating callbacks
    Given synthetic module callbacks with interrupted startup and shutdown
    When the authored core lifecycle methods execute
    Then cleanup retries preserve reverse order and do not repeat removed callbacks

  @AC-006
  Scenario: Reject salvage admission after failed core startup
    Given synthetic core state and registered native recipe objects
    When the authored crafting admission and registry audits execute
    Then stopped cores and mismatched recipes cannot authorize salvage

  @AC-004
  Scenario: Prepare pinned CE geometry candidates without inventing eligibility
    Given synthetic stock geometry diagnostic exports and hashed observations
    When the coverage candidate preparation tests execute
    Then drift invalid points and unrelated edits fail without native eligibility claims

  @AC-011
  Scenario: Recover private installation transactions without overwriting drift
    Given verified synthetic packages and isolated installation directories
    When install upgrade interrupted recovery and rollback tests execute
    Then unrelated files and drift are preserved without live deployment claims

  @AC-007 @AC-008
  Scenario: Bound supplementary infected propagation and restart recovery
    Given finite synthetic audible chain and persistent membership states
    When the infected completion policy and wiring tests execute
    Then propagation and recovery stay bounded without claiming native hearing or spawning

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

  @phase2 @offline
  Scenario: Recover group command ordering without replaying uncertain mutations
    Given synthetic sessions delayed snapshots and caller-owned requests
    When the authored group client recovery and retry methods execute
    Then request floors cannot rewind and uncertain payloads cannot change or replay across sessions

  @phase2 @offline
  Scenario: Preserve group map edits and native menu dispatch
    Given synthetic map widgets group snapshots and native menu collaborators
    When the authored map editing and menu dispatch methods execute
    Then edits retain server constraints and unrelated native menus remain available

  @phase2 @offline
  Scenario: Scale continuous stamina changes through the native handler
    Given synthetic native handler state and trusted bounded stamina settings
    When the authored stamina integration methods execute
    Then native event subtraction capacity clamps and permission handling remain authoritative

  @phase2 @offline
  Scenario: Read consistent bounded UTC snapshots for group expiry
    Given synthetic native date and time reads across midnight and clock rollback
    When the authored group UTC sampling methods execute
    Then invalid or inconsistent samples fail within the fixed retry bound

  @phase2 @offline
  Scenario: Exercise opt-in group policy fixtures without world side effects
    Given synthetic group DTO fixtures and a fixed step budget
    When the authored opt-in group check runner executes through offline adapters
    Then every operation and rejection must pass before a completion marker is emitted

  @phase2 @offline
  Scenario: Display bounded native stamina and carried-weight samples
    Given synthetic cached native load and stamina samples with widget collaborators
    When the authored stamina HUD sampling and display methods execute
    Then weight and stamina remain separate and hidden or invalid samples cannot display stale data

  @phase2 @offline
  Scenario: Track optional event progress only from admitted observations
    Given synthetic event definitions opted participants and ordered server observations
    When the authored bounded event director policies execute
    Then invalid transitions and replay cannot complete objectives or grant unimplemented rewards

  @phase2 @offline
  Scenario: Admit complete item export manifests without upgrading metadata to compatibility
    Given synthetic pinned item manifests and contiguous bounded configuration chunks
    When the strict item export consumer executes
    Then broken coverage and unsafe inputs fail while eligibility remains unqualified

  @phase2 @offline
  Scenario: Prepare bounded infected death observations without claiming rendered physics
    Given synthetic native interfaces stock missions and correlated result receipts
    When the infected death diagnostic preparation and result checks execute
    Then missing cleanup incomplete cases and outer timeouts cannot qualify the observation

  @phase2 @offline
  Scenario: Retain whole-content item and recipe evidence within bounded review work
    Given synthetic native rows and a complete source recipe census
    When the bounded whole-content review joins class and recipe evidence
    Then every input remains counted and truncated links never become gameplay approval

  @phase2 @offline
  Scenario: Authorize a single diagnostic fuel transfer without replay
    Given synthetic native vehicle vessel actor and action collaborators
    When the authored diagnostic fuel action guards and transfer methods execute
    Then unauthorized cancelled or replayed attempts cannot credit fuel

  @phase2 @offline
  Scenario: Prepare fuel observations without accepting an unobserved transfer
    Given synthetic installed interfaces fresh missions and correlated fuel receipts
    When the fixed fuel probe preparation and result validator execute
    Then missing conservation callbacks cleanup or timely completion reject the observation

  @phase2 @offline
  Scenario: Compare native stamina transport with bounded numeric tolerance
    Given synthetic native contexts and the observed finite quantization sample
    When the stamina transport control generator and numeric comparisons execute
    Then harmless rounding is accepted while mismatches and nonfinite fields fail

  @phase2 @offline
  Scenario: Schedule resource attraction only from bounded fresh native observations
    Given synthetic resource zones actor observations and explicit navigation capabilities
    When the authored ecology scheduling and receipt commit policies execute
    Then stale null oversized overflowing or replayed proposals cannot mutate assignments

  @phase2 @offline
  Scenario: Admit fuel receipts only inside an owned bounded native run
    Given synthetic process clocks isolated missions and fuel observation receipts
    When the fixed fuel runner enforces launch staging deadline and cleanup ownership
    Then startup late receipts foreign directories and surviving processes cannot pass

  @phase2 @offline
  Scenario: Require all death cases before the native probe deadline
    Given synthetic server logs process lifetimes and five-case death receipts
    When the receipt-aware native compiler harness evaluates the fixed death purpose
    Then initialization stale nonces late completion and missing cleanup cannot qualify the run

  @phase2 @offline
  Scenario: Activate stamina only from an opted-in trusted session configuration
    Given synthetic native configuration receipts server profiles and session callbacks
    When the authored stamina configuration loader and activation gates execute
    Then missing opt-in invalid profiles unauthenticated receipts and session resets cannot retain custom stamina

  @phase2 @offline
  Scenario: Retain whole-source action and item-use evidence without evaluating dispatch
    Given synthetic complete source trees with action registration calls and item callbacks
    When the bounded action census retains declarations controls and unresolved ancestry
    Then no omitted input ambiguous receiver or disabled reference becomes effective gameplay approval

  @phase2 @offline
  Scenario: Preserve taped-light identity while consuming tape on each mount
    Given synthetic qualified bindings inventory custody snapshots and journal receipts
    When the authored taped-light mount and hand-removal policies execute
    Then replay failed writes and changed identities cannot retry a move or refund consumed tape

  @phase2 @offline
  Scenario: Admit actor-free startup controls only from unchanged bounded evidence
    Given synthetic isolated native processes and nonce-bound startup receipts
    When the fixed startup runner checks staging publication deadlines and cleanup
    Then changed evidence uncertain reports and incomplete callbacks cannot pass admission

  @offline
  Scenario: Bind measured interior records without inventing layout qualification
    Given synthetic measured records pinned source documents and live house collaborators
    When the bounded interior import and contextual binding methods execute
    Then ambiguous houses invalid transforms and mismatched provenance cannot enable placement

  @offline
  Scenario: Preserve audited cutting tools through salvage registration and completion
    Given the complete audited cutting class set and synthetic native recipe collaborators
    When salvage registration eligibility and completion guards execute
    Then every supported tool retains its identity wear and material checks without native transaction claims

  @offline
  Scenario: Observe bounded owned-process counters without inferring engine liveness
    Given synthetic procfs identities counters log metadata and monotonic clocks
    When the bounded process observer samples explicit owned process and log inputs
    Then reuse missing data rollback and work limits remain explicit without readiness or deadlock claims
