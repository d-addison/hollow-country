"""Review confinement: prevent prohibited process launches, including fixture Git writes."""
import os
import sys

def guard(event, args):
    if event == 'subprocess.Popen':
        executable, argv = args[:2]
        name = os.path.basename(os.fsdecode(executable)).lower()
        if any(word in name for word in ('wine', 'powershell', 'pwsh', 'dayz')):
            raise PermissionError('WP1 review forbids game/Wine/PowerShell processes')
        if name == 'git':
            # Tests use init/add in synthetic fixtures; those are outside this review contract too.
            readonly = {'ls-files', 'check-ignore', 'rev-parse', 'ls-tree', 'show', 'diff'}
            if not any(str(arg) in readonly for arg in argv[1:]):
                raise PermissionError('WP1 review forbids Git mutation, including synthetic init/add')
sys.addaudithook(guard)
