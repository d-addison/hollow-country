# ADR-017: Local development for a small co-op server

- Status: Accepted by user, 2026-11-16.
- Supersedes ADR-001 / DEV-01 only where separate machines blocked local work.
  Develop and test server here; eventually deliver to friend's 3–6-player server.
- Name: Hollow Country. Map: ChernarusPlus confirmed. Repository stays private.
- Record shared-host contention; recalibrate on destination hardware. Two clients
  remain necessary for network, audio, visibility and race acceptance.
- Transfer only authored config/scripts and signed mod, without game assets,
  runtime storage or private key. Hash/signature checks, backup, clean install,
  smoke test and rollback are required before destination acceptance.
