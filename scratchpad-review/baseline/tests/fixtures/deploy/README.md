# Synthetic deployment scenarios

Package inputs are generated from original text in `test_deploy.py` using the
existing PBO/handoff writer. No game assets, keys or server destinations are
used. Profile bytes are opaque sentinels, not native save compatibility proof.

Checkpoint tests interrupt actual temporary filesystem operations at journal
publication, partial/complete staging, backup rename, activation, state commit
and receipt publication. These simulate process interruption, not physical
power loss or hostile concurrent directory replacement.

`deployment.feature` contains four scenarios executed by bindings in
`test_deploy.py`; unknown steps fail. Additional child processes really exit
without cleanup and parent-process recovery checks the filesystem and lock.
`tdd-red*.txt` preserves actual initial/regression failures; `tdd-green.txt`
records the final scoped test command's output.
