"""HC-E060: reject new assigned directly to a weak or inout parameter."""
import re

RULE = 'HC-E060'
DESCRIPTION = ('new assigned to a weak parameter (native compile: Variable is not strong ref) or an inout '
               'parameter (replaces the caller\'s object); own it in a strong local first; for inout, '
               'assign through an out parameter or a return value')
_TOKEN = re.compile(r'[A-Za-z_]\w*|[^\s]')


def findings(el, project, source):
    for method in source.methods:
        checked = {name: direction for _, name, direction in method.parameters(with_direction=True)
                   if direction != 'out'}
        if not checked:
            continue
        body = source.code[method.body_start:method.body_end]
        tokens = list(_TOKEN.finditer(body))
        for index in range(len(tokens) - 2):
            token = tokens[index]
            name = token.group()
            if name not in checked or [t.group() for t in tokens[index + 1:index + 3]] != ['=', 'new']:
                continue
            # A field can share the parameter's name, including this /* ... */ . name.
            if index and tokens[index - 1].group() == '.':
                continue
            if checked[name] == 'inout':
                message = (f"new assigned to inout parameter '{name}' replaces the caller's object; "
                           'own the new object in a strong local and assign through an out parameter '
                           'or a return value')
            else:
                message = (f"native compile: Variable '{name}' is not strong ref; own the new object "
                           'in a strong local (HCFuelSiphon.c:106-115 idiom)')
            yield el._finding(RULE, source, method.body_start + token.start(), f'{method.name}.{name}', message)
