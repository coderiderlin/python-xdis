#  Copyright (c) 2015, 2016 by Rocky Bernstein

"""
Python 3 Generic bytecode disassembler

This overlaps various Python3's dis module, but it can be run from
Python versions other than the version running this code. Notably,
run from Python version 2 and we save instruction information.
"""

from __future__ import print_function

import dis
import pyxdis.disasm.dis3 as dis3

from collections import namedtuple
from array import array

from pyxdis.code import iscode
from pyxdis.instruction import Instruction
from pyxdis.disassemble import Disassemble
from pyxdis import PYTHON3


# Get all the opcodes into globals
import pyxdis.opcodes.opcode_3x as op3

globals().update(op3.opmap)

import pyxdis.disassemble as disasm

class Disassemble3(Disassemble):

    def __init__(self, version):
        super(Disassemble3, self).__init__(version)

    def disassemble(self, co, classname=None, code_objects={}):
        """
        Generic Python disassembly
        """
        # Container for instructions
        instructions = []

        self.code = array('B', co.co_code)

        bytecode = dis3.Bytecode(co, self.opc)

        for inst in bytecode:
            pattr =  inst.argrepr
            opname = inst.opname
            instructions.append(
                Instruction(
                    type_ = opname,
                    attr = inst.argval,
                    pattr = pattr,
                    offset = inst.offset,
                    linestart = inst.starts_line,
                    )
                )
            pass
        return instructions

def _test(version):
    import inspect
    co = inspect.currentframe().f_code
    instructions = Disassemble3(version).disassemble(co)
    for i in instructions:
        print(i.format())

if __name__ == "__main__":
    from pyxdis import PYTHON_VERSION
    if PYTHON_VERSION >= 3.0:
        from pyxdis import PYTHON_VERSION
        _test(PYTHON_VERSION)
    else:
        print("Need to be Python 3.0 or greater to demo; I am %s." %
              PYTHON_VERSION)
    pass