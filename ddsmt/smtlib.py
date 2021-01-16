import re

from . import nodes
from .nodes import Node

# Stores all declared or defined (first-order) constants with their sorts
__constants = {}
# Stores all defined functions with their return sorts
__defined_functions = {}
# Stores the sorts for all declared or defined symbols
__sort_lookup = {}


def collect_information(exprs):
    """Initialize global lookups for first-order constants, defined functions
    and sorts of all these symbols."""
    global __constants
    global __defined_functions
    global __sort_lookup
    __constants = {}
    __defined_functions = {}
    __sort_lookup = {}

    for cmd in exprs:
        if not cmd.has_ident():
            continue
        name = cmd.get_ident()
        if name == 'declare-const':
            if not len(cmd) == 3:
                continue
            assert is_leaf(cmd[1])
            __constants[cmd[1].data] = cmd[2]
            __sort_lookup[cmd[1].data] = cmd[2]
        if name == 'declare-fun':
            if not len(cmd) == 4:
                continue
            assert cmd[1].is_leaf()
            assert not is_leaf(cmd[2])
            if cmd[2] == tuple():
                __constants[cmd[1].data] = cmd[2]
            __sort_lookup[cmd[1].data] = cmd[3]
        if name == 'define-fun':
            if not len(cmd) == 5:
                continue
            assert is_leaf(cmd[1])
            assert not is_leaf(cmd[2])
            if cmd[2] == tuple():
                __constants[cmd[1]] = cmd[2]
            __defined_functions[
                cmd[1]] = lambda args, cmd=cmd: nodes.substitute(
                    cmd[4], {cmd[2][i][0]: args[i]
                             for i in range(len(args))})
            __sort_lookup[cmd[1].data] = cmd[3]


def reset_information():
    """Reset global information gathered via collect_information.

    This is mainly to be used in the unit tests.
    """
    global __constants
    global __defined_functions
    global __sort_lookup
    __constants = {}
    __defined_functions = {}
    __sort_lookup = {}


### General utilities


def get_variables_with_sort(var_sort):
    """Return all variables with the sort :code:`var_sort`.

    Requires that global information has been populated via
    :code:`collect_information`.
    """
    return [v for v in __sort_lookup if __sort_lookup[v] == var_sort]


def introduce_variables(exprs, vars):
    """Adds new variables to a set of input expressions.

    Expects :code:`vars` to contain declaration commands (like
    :code:`declare-fun`). Inserts the variables into :code:`exprs`
    before the first SMT-LIB command that is not `set-info`, `set-logic`
    or a constant/function/variable declaration.
    """
    pos = 0
    while pos < len(exprs):
        e = exprs[pos]
        if not e.has_ident():
            break
        if not e.get_ident() in [
                'declare-const', 'declare-fun', 'define-fun', 'set-info',
                'set-logic'
        ]:
            break
        pos += 1
    return exprs[:pos] + vars + exprs[pos:]


def substitute_vars_except_decl(exprs, repl):
    """
    Perform the given variable substitution anywhere it occurs except in
    declaration commands :code:`declare-const`, :code:`declare-fun`,
    :code:`define-fun`.
    """
    res = []
    for e in exprs:
        if e.has_ident() and e.get_ident() in [
                'declare-const', 'declare-fun', 'define-fun'
        ]:
            res.append(e)
        else:
            res.append(nodes.substitute(e, repl))
    return res


### General semantic testers and testers


def is_leaf(node):
    """Check whether the :code:`node` is a leaf node."""
    return node.is_leaf()


def is_var(node):
    """Return true if :code:`node` is a variable (first order constant) node.

    Requires that global information has been populated via
    :code:`collect_information`.
    """
    return node.is_leaf() and node in __constants


def has_ident(node):
    """Check whether the :code:`node` has a name, that is its first child is a
    leaf node."""
    return not node.is_leaf() and not node == () and is_leaf(node[0])


def get_ident(node):
    """Get the name of the :code:`node`, asserting that
    :code:`has_ident(node)`."""
    assert has_ident(node)
    return node[0]


def is_piped_symbol(node):
    """Checks whether the :code:`node` is a quoted symbol."""
    return node.is_leaf() and node[0] == '|' and node[-1] == '|'


def get_piped_symbol(node):
    """Returns the actual symbol name from a quoted symbol :code:`node`."""
    assert is_piped_symbol(node)
    return Node(node[1:-1])


def is_operator_app(node, name):
    return has_ident(node) and get_ident(node) == name


def is_indexed_operator(node, name, index_count=1):
    """Return true if :code:`node` is an indexed operator :code:`name` and the
    given number of indices matches :code:`index_count`."""
    if node.is_leaf() or len(node) < 2:
        return False
    if has_ident(node) and get_ident(node) != '_':
        return False
    if node[1] != name:
        return False
    return len(node) == index_count + 2


def is_indexed_operator_app(node, name, index_count=1):
    return len(node) > 0 and is_indexed_operator(node[0], name, index_count)


def has_nary_operator(node):
    """Check whether :code:`node` is an application of an n-ary operator."""
    if node.is_leaf() or not has_ident(node):
        return False
    return get_ident(node) in [
        '=>',
        'and',
        'or',
        'xor',
        '=',
        'distinct',
        '+',
        '-',
        '*',
        'div',
        '/',
        '<=',
        '<',
        '>=',
        '>',
        'bvand',
        'bvor',
        'bvadd',
        'bvmul',
        'concat',
        'fp.lt',
        'fp.gt',
        'fp.leq',
        'fp.geq',
    ]


def is_const(node):
    """Return true if :code:`node` is a constant value."""
    return is_bool_const(node) or is_arith_const(node) or is_int_const(
        node) or is_real_const(node) or is_string_const(node) or is_bv_const(
            node)


def is_eq(node):
    """Checks whether :code:`node` is an equality."""
    return has_ident(node) and get_ident(node) == '='


def get_constants(sort):
    """Return a list of default constants for the given :code:`sort`."""
    if sort == 'Bool':
        return [Node('false'), Node('true')]
    if sort == 'Int':
        return [Node('0'), Node('1')]
    if sort == 'Real':
        return [Node('0.0'), Node('1.0')]
    if is_bv_sort(sort):
        return [Node('_', c, sort[2]) for c in ['bv0', 'bv1']]
    if is_set_sort(sort):
        return [Node('as', 'emptyset', sort)] \
               + [Node('singleton', c) for c in get_constants(sort[1])]
    return []


def get_sort(node):
    """Get the sort of the given node.

    Return :code:`None` if it can not be inferred.
    Requires that global information has been populated via
    :code:`collect_information`.
    """
    if node.is_leaf() and node.data in __sort_lookup:
        return __sort_lookup[node.data]
    if is_bool_const(node):
        return Node('Bool')
    if is_bv_const(node):
        return Node('_', 'BitVec', str(get_bv_width(node)))
    if is_int_const(node):
        return Node('Int')
    if is_real_const(node):
        return Node('Real')
    bvwidth = get_bv_width(node)
    # operators the return bit-vectors handled via get_bv_width
    if bvwidth != -1:
        return Node('_', 'BitVec', str(bvwidth))
    # non-indexed operators
    if has_ident(node) and len(node) > 1:
        if is_operator_app(node, 'ite') and len(node) > 2:
            return get_sort(node[2])
        ident = get_ident(node)
        # operators that return Bool
        if ident in [
                # core theory
                'not',
                '=>',
                'and',
                'or',
                'xor',
                '=',
                'distinct',
                # bv theory
                'bvult',
                'bvule',
                'bvugt',
                'bvuge',
                'bvslt',
                'bvsle',
                'bvsgt',
                'bvsge',
                # fp theory
                'fp.leq',
                'fp.lt',
                'fp.geq',
                'fp.gt',
                'fp.eq',
                'fp.isNormal',
                'fp.isSubnormal',
                'fp.isZero',
                'fp.isInfinite',
                'fp.isNaN',
                'fp.isNegative',
                'fp.isPositive',
                # int / real theory
                '<=',
                '<',
                '>>',
                '>',
                'is_int',
                # sets theory
                'member',
                'subset',
                # string theory
                'str.<',
                'str.in_re',
                'str.<=',
                'str.prefixof',
                'str.suffixof',
                'str.contains',
                'str.is_digit',
        ]:
            return Node('Bool')
        # operators that return Int
        if ident in [
                'div',
                'mod',
                'abs',
                'to_int',
                # string theory
                'str.len',
                'str.indexof',
                'str.to_code',
                'str.to_int',
                # sets theory
                'card'
        ]:
            return Node('Int')
        # operators that return Real
        if ident in ['/', 'to_real', 'fp.to_real']:
            return Node('Real')
        if ident in ['+', '-', '*']:
            if any(map(lambda n: get_sort(n) == 'Real', node[1:])):
                return Node('Real')
            elif get_sort(node[1]) == 'Int':
                return Node('Int')
            else:
                return None
        # operators that return floating-points
        if ident in [
                'fp.abs',
                'fp.max',
                'fp.min',
                'fp.neg',
                'fp.rem',
        ]:
            return get_sort(node[1])
        if ident in [
                'fp.add',
                'fp.div',
                'fp.fma',
                'fp.mul',
                'fp.roundToIntegral',
                'fp.sqrt',
                'fp.sub',
        ]:
            return get_sort(node[2])
        if ident == 'fp':
            ew = get_bv_width(node[2])
            sw = 1 + get_bv_width(node[3])
            return Node('_', 'FloatingPoint', ew, sw)

    ## indexed operators
    if is_indexed_operator_app(node, 'divisible'):
        return Node('Bool')
    if is_indexed_operator_app(node, 'to_fp', 2) \
       or is_indexed_operator_app(node, 'to_fp_unsigned', 2):
        idx = get_indices(node[0], node[0][1], 2)
        return Node('_', 'FloatingPoint', idx[0], idx[1])
    if is_indexed_operator_app(node, 'fp.to_sbv', 1) \
       or is_indexed_operator_app(node, 'fp.to_ubv', 1):
        return Node('_', 'BitVec', get_indices(node[0], node[0][1], 1)[0])

    return None


def get_indices(node, name, index_count=1):
    """Return a list with the indices of the given indexed operator."""
    assert is_indexed_operator(node, name, index_count)
    return [int(n.data) for n in node[2:]]


### Boolean


def is_bool_const(node):
    """Return true if :code:`node` is a Boolean constant."""
    return node.is_leaf() and node.data in ['false', 'true']


### Arithmetic


def is_arith_const(node):
    """Return true if :code:`node` is an arithmetic constant."""
    if has_ident(node) and get_ident(node) == '/' and len(node) == 3:
        return is_int_const(node[1]) and is_int_const(node[2])
    return node.is_leaf() \
           and re.match('[0-9]+(\\.[0-9]*)?$', node.data) is not None


def is_int_const(node):
    """Return true if :code:`node` is an int constant."""
    return node.is_leaf() and re.match('^[0-9]+$', node.data) is not None


def is_real_const(node):
    """Return true if :code:`node` is a real constant."""
    if has_ident(node) and get_ident(node) == '/' and len(node) == 3:
        return is_int_const(node[1]) and is_int_const(node[2])
    return node.is_leaf() \
           and re.match('^[0-9]+(\\.[0-9]*)?$', node.data) is not None


### BV


def is_bv_sort(node):
    """Return true if :code:`node` is a bit-vector sort."""
    if node.is_leaf() or len(node) != 3:
        return False
    if not has_ident(node) or get_ident(node) != '_':
        return False
    return node[1] == 'BitVec'


def is_bv_const(node):
    """Return true if :code:`node` is a bit-vector constant."""
    if node.is_leaf():
        s = node.data
        if s.startswith('#b'):
            return True
        if s.startswith('#x'):
            return True
        return False
    if len(node) != 3:
        return False
    if not node.has_ident() or node.get_ident() != '_':
        return False
    if not node.data[1].is_leaf():
        return False
    return node.data[1].data.startswith('bv')


def is_bv_comp(node):
    """Checks whether :code:`node` is a bit-vector comparison."""
    return has_ident(node) and get_ident(node) == 'bvcomp'


def is_bv_not(node):
    """Checks whether :code:`node` is a bit-vector bit-wise negation."""
    return has_ident(node) and get_ident(node) == 'bvnot'


def is_bv_neg(node):
    """Checks whether :code:`node` is a bit-vector negation."""
    return has_ident(node) and get_ident(node) == 'bvneg'


def get_bv_width(node):
    """Return the bit-width of a bit-vector node.

    Asserts that :code:`node` is a bit-vector node.
    Requires that global information has been populated via
    :code:`collect_information`.
    """
    if is_bv_const(node):
        if node.is_leaf():
            data = node.data
            if data.startswith('#b'):
                return len(data[2:])
            if data.startswith('#x'):
                return len(data[2:]) * 4
        return int(node[2].data)
    if node in __sort_lookup:
        bvsort = __sort_lookup[node]
        if is_bv_sort(bvsort):
            return int(bvsort[2].data)
        else:
            return -1
    if is_indexed_operator_app(node, 'zero_extend') \
       or is_indexed_operator_app(node, 'sign_extend'):
        return get_indices(node[0], node[0][1])[0] + get_bv_width(node[1])
    if is_indexed_operator_app(node, 'extract', 2):
        idx = get_indices(node[0], 'extract', 2)
        return idx[0] - idx[1] + 1
    if is_indexed_operator_app(node, 'repeat'):
        return get_indices(node[0], 'repeat')[0] * get_bv_width(node[1])
    if is_indexed_operator_app(node, 'rotate_left') \
       or is_indexed_operator_app(node, 'rotate_right'):
        return get_bv_width(node[1])
    if is_indexed_operator_app(node, 'fp.to_ubv') \
       or is_indexed_operator_app(node, 'fp.to_sbv'):
        return get_indices(node[0], node[0][1])[0]
    if node.has_ident():
        ident = node.get_ident()
        if ident in [
                'bvadd',
                'bvand',
                'bvashr',
                'bvmul',
                'bvnand',
                'bvneg',
                'bvnor',
                'bvnot',
                'bvor',
                'bvsdiv',
                'bvshl',
                'bvshr',
                'bvsmod',
                'bvsrem',
                'bvsub',
                'bvudiv',
                'bvurem',
                'bvxnor',
                'bvxor',
        ]:
            return get_bv_width(node[1])
        if ident == 'concat':
            assert len(node) == 3
            return get_bv_width(node[1]) + get_bv_width(node[2])
        if ident == 'bvcomp':
            return 1
        if ident == 'ite':
            bw = get_bv_width(node[2])
            if bw > 0:
                return bw
    return -1


def get_bv_constant_value(node):
    """
    Assume that node is a bit-vector constant and return
    :code:`(value, bit-width)`.
    """
    assert is_bv_const(node)
    if node.is_leaf():
        if node.data.startswith('#b'):
            return (int(node[2:], 2), len(node[2:]))
        assert node.data.startswith('#x')
        return (int(node[2:], 16), len(node[2:]) * 4)
    return (int(node[1][2:]), int(node[2].data))


### FP


def is_fp_sort(node):
    """Return true if :code:`node` is a floating-point sort."""
    if is_leaf(node) \
       and str(node).startswith('Float') \
       and node[5:] in ['16', '32', '64', '128']:
        return True
    if not has_ident(node) or get_ident(node) != '_' or len(node) != 4:
        return False
    return node[1] == 'FloatingPoint'


### Functions


def is_defined_fun(node):
    """Check whether :code:`node` is a defined function.

    Requires that global information has been populated via
    :code:`collect_information`.
    """
    if node.is_leaf():
        return node in __defined_functions
    return has_ident(node) and get_ident(node) in __defined_functions


def get_defined_fun(node):
    """Return the defined function :code:`node`, instantiated with the
    arguments of :code:`node` if necessary.

    Assumes :code:`is_defined_fun(node)`.
    Requires that global information has been populated via
    :code:`collect_information`.
    """
    assert is_defined_fun(node)
    if node.is_leaf():
        return __defined_functions[node.data]([])
    return __defined_functions[get_ident(node)](node[1:])


### Sets


def is_set_sort(node):
    """Return true if :code:`node` is a set sort."""
    if node.is_leaf() or len(node) != 2:
        return False
    if not has_ident(node) or get_ident(node) != 'Set':
        return False
    return True


### Strings


def is_string_const(node):
    """Checks whether the :code:`node` is a string constant."""
    return node.is_leaf() and re.match('^\"[^\"]*\"$', node.data) is not None
