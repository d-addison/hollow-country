# First Hollow Country package and native smoke attempt

Status: authored package verified offline; native compilation/loading blocked.
T004, FR-002, AC-002, NET-006/008 remain incomplete. Client connection is deferred
by the user; the compiler smoke does not require it.

The unsigned 0.1.0-dev PBO contains config.cpp plus 21 authored scripts, exact
prefix HollowCountry. The private ZIP includes mod metadata, operator defaults,
empty CE defaults, policy profiles, install/rollback documentation and helpers.
No game assets, vanilla dump, keys or runtime profiles are included.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| hollowcountry-0.1.0-dev.pbo | 111878 | 8fbd05ca43f2d3e9b33c87f7955158da3d1c0e322057766d6b57f9532d3f388a |
| hollow-country-0.1.0-dev.zip | 187836 | 7083e9662b45523e2eda70c88c0e888c461d2557bf5e217a7cfa4ec8665bae0b |

Outputs are in `C:\Users\David\Downloads\HollowCountry-Development-20261116`.
The verified ZIP was extracted into its fresh `handoff` subdirectory, so native
Windows does not need a WSL UNC path. Strict container/checksum/manifest/source
verification passed. Checksums are neither official signatures nor acceptance.

Read-only inspection found native Python at
`C:\Users\David\AppData\Local\Programs\Python\Python312\python.exe`, embedded
version 3.12.10. Its actual execution remains unverified.

Main attempted native Windows PowerShell with the extracted
`tools\package\Invoke-NativeSmoke.ps1`, the verified PBO, that Python path,
fresh `D:\HollowCountryLocal\native-smoke-001`, and MaxSeconds=180. The outer
Linux command had a 210-second limit; the helper itself bounds and stops only
its own isolated process. No client launch was requested.

Actual result: exit 1 before helper execution:
`WSL ERROR: UtilAcceptVsock:271: accept4 failed 110`.
The requested native runtime directory was not created. No Enforce compiler
output, native self-test result, Hollow Country server load or signature proof
exists from this attempt. The earlier vanilla run is separate evidence.

Next executable gate is the same reviewed native helper through a working
Windows launch path, followed by Diag/normal signed loading. All gameplay gaps
and remaining experiments are in [module status](../docs/MODULE_STATUS.md).
Keep feature flags false and do not transfer this development build to a live
friend server as a completed overhaul.
