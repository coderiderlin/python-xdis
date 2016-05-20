"""Disassembler of Python byte code into mnemonics.
Extracted from Python 2 and 3's dis module but generalized to
allow disassembling Python 2 bytecode on Python 3.
"""

# FIXME: can this be merged with dis3.py?

from dis import findlinestarts
import types
import collections
import io

from pyxdis import PYTHON3

if PYTHON3:
    def code2num(code, i):
        return code[i]
else:
    def code2num(code, i):
        return ord(code[i])

_have_code = (types.MethodType, types.FunctionType, types.CodeType, type)

def _try_compile(source, name):
    """Attempts to compile the given source, first as an expression and
       then as a statement if the first approach fails.

       Utility function to accept strings in functions that otherwise
       expect code objects
    """
    try:
        c = compile(source, name, 'eval')
    except SyntaxError:
        c = compile(source, name, 'exec')
    return c

def dis(x=None):
    """Disassemble classes, methods, functions, generators, or code.
    """
    if x is None:
        distb()
        return
    if hasattr(x, '__func__'):  # Method
        x = x.__func__
    if hasattr(x, '__code__'):  # Function
        x = x.__code__
    if hasattr(x, 'gi_code'):  # Generator
        x = x.gi_code
    if hasattr(x, '__dict__'):  # Class or module
        items = sorted(x.__dict__.items())
        for name, x1 in items:
            if isinstance(x1, _have_code):
                print("Disassembly of %s:" % name, file)
                try:
                    dis(x1, file)
                except TypeError as msg:
                    print("Sorry:", msg)
                print(file)
    elif isinstance(x, (bytes, bytearray)): # Raw bytecode
        _disassemble_bytes(x, file)
    else:
        raise TypeError("don't know how to disassemble %s objects" %
                        type(x).__name__)

def _get_code_object(x):
    """Helper to handle methods, functions, generators, strings and raw code objects"""
    if hasattr(x, '__func__'): # Method
        x = x.__func__
    if hasattr(x, '__code__'): # Function
        x = x.__code__
    if hasattr(x, 'gi_code'):  # Generator
        x = x.gi_code
    if isinstance(x, str):     # Source code
        x = _try_compile(x, "<disassembly>")
    if hasattr(x, 'co_code'):  # Code object
        return x
    raise TypeError("don't know how to disassemble %s objects" %
                    type(x).__name__)

def code_info(x):
    """Formatted details of methods, functions, or code."""
    return _format_code_info(_get_code_object(x))

def show_code(co):
    """Print details of methods, functions, or code to *file*.

    If *file* is not provided, the output is printed on stdout.
    """
    print(code_info(co))

_Instruction = collections.namedtuple("_Instruction",
     "opname opcode arg argval argrepr offset starts_line is_jump_target")

class Instruction2(_Instruction):
    """Details for a bytecode operation

       Defined fields:
         opname - human readable name for operation
         opcode - numeric code for operation
         arg - numeric argument to operation (if any), otherwise None
         argval - resolved arg value (if known), otherwise same as arg
         argrepr - human readable description of operation argument
         offset - start index of operation within bytecode sequence
         starts_line - line started by this opcode (if any), otherwise None
         is_jump_target - True if other code jumps to here, otherwise False
    """

    def _disassemble(self, lineno_width=3, mark_as_current=False):
        """Format instruction details for inclusion in disassembly output

        *lineno_width* sets the width of the line number field (0 omits it)
        *mark_as_current* inserts a '-->' marker arrow as part of the line
        """
        fields = []
        # Column: Source code line number
        if lineno_width:
            if self.starts_line is not None:
                lineno_fmt = "%%%dd" % lineno_width
                fields.append(lineno_fmt % self.starts_line)
            else:
                fields.append(' ' * lineno_width)
        # Column: Current instruction indicator
        if mark_as_current:
            fields.append('-->')
        else:
            fields.append('   ')
        # Column: Jump target marker
        if self.is_jump_target:
            fields.append('>>')
        else:
            fields.append('  ')
        # Column: Instruction offset from start of code sequence
        fields.append(repr(self.offset).rjust(4))
        # Column: Opcode name
        fields.append(opname.ljust(20))
        # Column: Opcode argument
        if self.arg is not None:
            fields.append(repr(self.arg).rjust(5))
            # Column: Opcode argument details
            if self.argrepr:
                fields.append('(' + self.argrepr + ')')
        return ' '.join(fields).rstrip()

    ## FIXME: figure out how to do _disassemble passing in opnames

def get_instructions(x, opc, first_line=None):
    """Iterator for the opcodes in methods, functions or code

    Generates a series of Instruction named tuples giving the details of
    each operations in the supplied code.

    If *first_line* is not None, it indicates the line number that should
    be reported for the first source line in the disassembled code.
    Otherwise, the source line information (if any) is taken directly from
    the disassembled code object.
    """
    co = _get_code_object(x)
    cell_names = co.co_cellvars + co.co_freevars
    linestarts = dict(findlinestarts(co))
    if first_line is not None:
        line_offset = first_line - co.co_firstlineno
    else:
        line_offset = 0
    return _get_instructions_bytes(co.co_code, opc, co.co_varnames, co.co_names,
                                   co.co_consts, cell_names, linestarts,
                                   line_offset)

def _get_instructions_bytes(code, opc, varnames=None, names=None, constants=None,
                      cells=None, linestarts=None, line_offset=0):
    """Iterate over the instructions in a bytecode string.

    Generates a sequence of Instruction namedtuples giving the details of each
    opcode.  Additional information about the code's runtime environment
    (e.g. variable names, constants) can be specified using optional
    arguments.

    """
    opnames = opc.opname
    labels = findlabels(code, opc)
    extended_arg = 0
    starts_line = None
    # enumerate() is not an option, since we sometimes process
    # multiple elements on a single pass through the loop
    n = len(code)
    i = 0
    while i < n:
        op = code2num(code, i)
        offset = i
        if linestarts is not None:
            starts_line = linestarts.get(i, None)
            if starts_line is not None:
                starts_line += line_offset
        is_jump_target = i in labels
        i = i+1
        arg = None
        argval = None
        argrepr = ''
        if op >= opc.HAVE_ARGUMENT:
            arg = code2num(code, i) + code2num(code, i+1)*256 + extended_arg
            extended_arg = 0
            i = i+2
            if op == opc.EXTENDED_ARG:
                extended_arg = arg*65536
            #  Set argval to the dereferenced value of the argument when
            #  availabe, and argrepr to the string representation of argval.
            #    _disassemble_bytes needs the string repr of the
            #    raw name index for LOAD_GLOBAL, LOAD_CONST, etc.
            argval = arg
            if op in opc.hasconst:
                argval, argrepr = _get_const_info(arg, constants)
            elif op in opc.hasname:
                opc.argval, opc.argrepr = _get_name_info(arg, names)
            elif op in opc.hasjrel:
                argval = i + arg
                argrepr = "to " + repr(argval)
            elif op in opc.haslocal:
                argval, argrepr = _get_name_info(arg, varnames)
            elif op in opc.hascompare:
                argval = opc.cmp_op[arg]
                argrepr = argval
            elif op in opc.hasfree:
                argval, argrepr = _get_name_info(arg, cells)
            elif op in opc.hasnargs:
                argrepr = ("%d positional, %d keyword pair" %
                               (code2num(code, i-2), code2num(code, i-1)))
        opname = opnames[op]
        yield Instruction2(opname, op, arg, argval, argrepr,
                          offset, starts_line, is_jump_target)

def _get_const_info(const_index, const_list):
    """Helper to get optional details about const references

       Returns the dereferenced constant and its repr if the constant
       list is defined.
       Otherwise returns the constant index and its repr().
    """
    argval = const_index
    if const_list is not None:
        argval = const_list[const_index]

    return argval, repr(argval)

def _get_name_info(name_index, name_list):
    """Helper to get optional details about named references

       Returns the dereferenced name as both value and repr if the name
       list is defined.
       Otherwise returns the name index and its repr().
    """
    argval = name_index
    if name_list is not None:
        argval = name_list[name_index]
        argrepr = argval
    else:
        argrepr = repr(argval)
    return argval, argrepr

def findlabels(code, opc):
    """Detect all offsets in a byte code which are jump targets.

    Return the list of offsets.

    """
    labels = []
    # enumerate() is not an option, since we sometimes process
    # multiple elements on a single pass through the loop
    n = len(code)
    i = 0
    while i < n:
        op = code2num(code, i)
        i = i+1
        if op >= opc.HAVE_ARGUMENT:
            arg = code2num(code, i) + code2num(code, i+1)*256
            i = i+2
            label = -1
            if op in opc.hasjrel:
                label = i+arg
            elif op in opc.hasjabs:
                label = arg
            if label >= 0:
                if label not in labels:
                    labels.append(label)
    return labels

class Bytecode:
    """The bytecode operations of a piece of code

    Instantiate this with a function, method, string of code, or a code object
    (as returned by compile()).

    Iterating over this yields the bytecode operations as Instruction instances.
    """
    def __init__(self, x, opnames, first_line=None, current_offset=None):
        self.codeobj = co = _get_code_object(x)
        if first_line is None:
            self.first_line = co.co_firstlineno
            self._line_offset = 0
        else:
            self.first_line = first_line
            self._line_offset = first_line - co.co_firstlineno
        self._cell_names = co.co_cellvars + co.co_freevars
        self._linestarts = dict(findlinestarts(co))
        self._original_object = x
        self.opnames = opnames
        self.current_offset = current_offset

    def __iter__(self):
        co = self.codeobj
        return _get_instructions_bytes(co.co_code, self.opnames, co.co_varnames, co.co_names,
                                       co.co_consts, self._cell_names,
                                       self._linestarts,
                                       line_offset=self._line_offset)

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__,
                                 self._original_object)

    @classmethod
    def from_traceback(cls, tb):
        """ Construct a Bytecode from the given traceback """
        while tb.tb_next:
            tb = tb.tb_next
        return cls(tb.tb_frame.f_code, current_offset=tb.tb_lasti)

    def info(self):
        """Return formatted information about the code object."""
        return _format_code_info(self.codeobj)

    def dis(self):
        """Return a formatted view of the bytecode operations."""
        co = self.codeobj
        if self.current_offset is not None:
            offset = self.current_offset
        else:
            offset = -1
        with io.StringIO() as output:
            _disassemble_bytes(co.co_code, varnames=co.co_varnames,
                               names=co.co_names, constants=co.co_consts,
                               cells=self._cell_names,
                               linestarts=self._linestarts,
                               line_offset=self._line_offset,
                               file=output,
                               lasti=offset)
            return output.getvalue()