"""HC-E060: native compile rejects new assigned directly to a weak parameter."""
import re

RULE = 'HC-E060'
DESCRIPTION = 'new assigned to a non-out/inout parameter (native compile: Variable is not strong ref); own it in a strong local first'
_TOKEN = re.compile(r'[A-Za-z_]\w*|[^\s]')


def findings(el, project, source):
    for method in source.methods:
        weak = {name for _, name, is_out in method.parameters() if not is_out}
        if not weak:
            continue
        body = source.code[method.body_start:method.body_end]
        tokens = list(_TOKEN.finditer(body))
        for index in range(len(tokens) - 2):
            token = tokens[index]
            name = token.group()
            if name not in weak or [t.group() for t in tokens[index + 1:index + 3]] != ['=', 'new']:
                continue
            # A field can share the parameter's name, including this /* ... */ . name.
            if index and tokens[index - 1].group() == '.':
                continue
            yield el._finding(
                RULE, source, method.body_start + token.start(), f'{method.name}.{name}',
                f"native compile: Variable '{name}' is not strong ref; own the new object "
                'in a strong local (HCFuelSiphon.c:106-115 idiom)')
