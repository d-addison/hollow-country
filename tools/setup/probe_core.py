"""Shared, launch-free primitives for future probe/stager migrations.

Path translation is lexical and covers drive-mounted WSL paths only. It does
not resolve links or invoke Windows interop. Call ``safe`` separately for local
filesystem checks. Host leases reuse the existing WSL host-lock implementation;
they must enclose the entire native operation, including staging and cleanup.
"""
import os
from pathlib import Path, PureWindowsPath
import re
import stat


def _path_text(value):
    value = os.fspath(value)
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ValueError('path must be nonempty text without control characters')
    return value


def _drive_parts(parts):
    reserved = re.compile(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', re.I)
    for part in parts:
        if (part in {'.', '..'} or part.endswith((' ', '.'))
                or any(c in part for c in '<>:"|?*') or reserved.fullmatch(part)):
            raise ValueError('path component is not a plain Windows name')


def windows_path(path):
    """Translate /mnt/<drive>[/...] to an absolute Windows drive path.

    UNC, relative paths, traversal and Windows-normalized aliases are refused.
    The result is data: use ``quote_ps`` when embedding it in PowerShell.
    """
    value = _path_text(path)
    match = re.fullmatch(r'/mnt/([a-zA-Z])(?:/(.*))?', value)
    if not match or '\\' in value:
        raise ValueError('expected an absolute WSL drive path')
    parts = (match[2] or '').rstrip('/').split('/') if match[2] else []
    if any(not part for part in parts):
        raise ValueError('empty path component refused')
    _drive_parts(parts)
    return str(PureWindowsPath(match[1].upper() + ':\\', *parts))


def linux_path(path):
    """Translate an absolute Windows drive path to its /mnt/<drive> Path."""
    value = _path_text(path).replace('\\', '/')
    match = re.fullmatch(r'([a-zA-Z]):/(.*)', value)
    if not match:
        raise ValueError('expected an absolute Windows drive path')
    parts = match[2].rstrip('/').split('/') if match[2] else []
    if any(not part for part in parts):
        raise ValueError('empty path component refused')
    _drive_parts(parts)
    return Path('/mnt') / match[1].lower() / Path(*parts)


def quote_ps(value):
    """One literal PowerShell string argument, including empty/apostrophe values.

    This quotes PowerShell syntax, not cmd.exe or a native Windows command line.
    """
    value = str(value)
    if any(ord(c) < 32 for c in value):
        raise ValueError('control characters forbidden in PowerShell arguments')
    return "'" + value.replace("'", "''") + "'"


def safe(path):
    """Return an absolute local path after refusing linked/reparse components.

    Missing suffixes are allowed for fresh staging destinations. Permission and
    other inspection errors propagate. This is a preflight check, not protection
    against concurrent filesystem replacement: use descriptor-based no-follow I/O
    (as probe_runtime does) for actual reads and writes. Isolation policies belong
    to each stager; this helper does not authorize a destination for mutation.
    """
    value = _path_text(path)
    path = Path(value)
    if '..' in path.parts:
        raise ValueError('parent traversal refused')
    path = path.absolute()
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError('linked/reparse path refused')
    return path


def host_lock(holder, path=None):
    """Use the canonical host lease, including descendant reentry/refusal.

    Import lazily so staging-only users need no platform-specific lock module.
    Contention raises tools.release.host_lock.LockRefused; no second lock or
    independent environment token is introduced here.
    """
    from tools.release.host_lock import host_lock as shared_host_lock
    return shared_host_lock(holder, path)


def enforce_json_helpers(*, max_string_bytes=96):
    """Return self-contained HCProbe JSON methods for insertion into a class.

    Strings are bounded before escaping, preserving quotes, slashes and ASCII
    controls as JSON escapes. Number methods require finite engine values. This
    emits source only: native compilation/runtime evidence remains a lead gate.
    """
    if type(max_string_bytes) is not int or not 1 <= max_string_bytes <= 4096:
        raise ValueError('string byte bound must be an integer in 1..4096')
    return r'''
    string HCProbeStr(string value)
    {
        int quoteCode = 34;
        int slashCode = 92;
        string quote = quoteCode.AsciiToString();
        string slash = slashCode.AsciiToString();
        string hex = "0123456789abcdef";
        string text = quote;
        int limit = value.Length();
        if (limit > @LIMIT@)
            limit = @LIMIT@;
        for (int index = 0; index < limit; index++)
        {
            string character = value.Get(index);
            int code = character.ToAscii();
            if (code == quoteCode || code == slashCode)
                text = text + slash + character;
            else if (code >= 0 && code < 32)
            {
                int high = code / 16;
                int low = code % 16;
                text = text + slash + "u00" + hex.Get(high) + hex.Get(low);
            }
            else
                text = text + character;
        }
        return text + quote;
    }

    string HCProbeKey(string name)
    {
        return HCProbeStr(name) + ":";
    }

    string HCProbeBool(bool value)
    {
        if (value)
            return "true";
        return "false";
    }

    string HCProbeInt(int value)
    {
        return value.ToString();
    }

    string HCProbeNum(float value)
    {
        return value.ToString();
    }

    string HCProbeVector(vector value)
    {
        return "[" + HCProbeNum(value[0]) + "," + HCProbeNum(value[1]) + "," + HCProbeNum(value[2]) + "]";
    }
'''.replace('@LIMIT@', str(max_string_bytes))


def enforce_sanitizing_json_helpers(prefix, quote, slash, *, vector='tostring', max_string_bytes=96):
    """Return the Key/Str/Bool/Vector methods of a sanitizing (lossy) JSON text emitter.

    Unlike ``enforce_json_helpers`` these methods never escape: the string is
    bounded, then quote characters become an apostrophe and backslashes become a
    slash, so consumers of existing probe output keep one-token-per-string rows.
    ``prefix`` names the generated methods (``<prefix>Key`` ...); ``quote`` and
    ``slash`` name hook members already holding the one-character strings.
    ``vector`` is ``tostring`` (explicit ``.ToString()`` per component) or ``plain``
    (implicit conversion). Source only: native compilation stays a lead gate.
    """
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', prefix):
        raise ValueError('method prefix must be an identifier')
    for name in (quote, slash):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', name):
            raise ValueError('member names must be identifiers')
    if vector not in ('tostring', 'plain'):
        raise ValueError('vector style must be tostring or plain')
    if type(max_string_bytes) is not int or not 1 <= max_string_bytes <= 4096:
        raise ValueError('string byte bound must be an integer in 1..4096')
    suffix = '.ToString()' if vector == 'tostring' else ''
    parts = ' + "," + '.join('value[%d]%s' % (axis, suffix) for axis in range(3))
    return r'''    string @P@Key(string name)
    {
        return @Q@ + name + @Q@ + ":";
    }

    string @P@Str(string value)
    {
        string text = value;
        if (text.Length() > @LIMIT@)
            text = text.Substring(0, @LIMIT@);
        text.Replace(@Q@, "'");
        text.Replace(@S@, "/");
        return @Q@ + text + @Q@;
    }

    string @P@Bool(bool value)
    {
        if (value)
            return "true";
        return "false";
    }

    string @P@Vector(vector value)
    {
        return "[" + @VEC@ + "]";
    }'''.replace('@P@', prefix).replace('@Q@', quote).replace('@S@', slash).replace(
        '@LIMIT@', str(max_string_bytes)).replace('@VEC@', parts)
