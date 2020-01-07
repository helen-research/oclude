import os
from sys import stderr

class MessagePrinter(object):
    def __init__(self, arg):
        self.prompt = '[' + arg.split('.')[0] +  ']'
    def __call__(self, message, prompt=True, nl=True):
        if prompt and nl:
            stderr.write(f'{self.prompt} {message}\n')
        elif prompt:
            stderr.write(f'{self.prompt} {message}')
        else:
            stderr.write(message)

llvm_instructions = ['add', 'sub', 'mul', 'udiv', 'sdiv', 'urem', 'srem',
                     'fneg', 'fadd', 'fsub', 'fmul', 'fdiv', 'frem', 'shl',
                     'lshr', 'ashr', 'and', 'or', 'xor', 'extractelement',
                     'insertelement', 'shufflevector', 'extractvalue', 'insertvalue',
                     'alloca', 'load', 'store', 'fence', 'cmpxchg', 'atomicrmw', 'getelementptr',
                     'ret', 'br', 'switch', 'indirectbr', 'invoke', 'call', 'callbr', 'resume', 'catchswitch',
                     'catchret', 'cleanupret', 'unreachable', 'trunc', 'zext', 'sext', 'fptrunc', 'fpext',
                     'fptoui', 'fptosi', 'uitofp', 'sitofp', 'ptrtoint', 'inttoptr', 'bitcast', 'addrspacecast',
                     'icmp', 'fcmp', 'phi', 'select', 'freeze', 'call', 'va_arg',
                     'landingpad', 'catchpad', 'cleanuppad']

tempfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.oclude_tmp_instr_src.cl')
templlvm = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.oclude_tmp_instr_ll.ll')

hidden_counter_name_local = 'ocludeHiddenCounterLocal'
hidden_counter_name_global = 'ocludeHiddenCounterGlobal'

epilogue = f'''barrier(CLK_LOCAL_MEM_FENCE | CLK_GLOBAL_MEM_FENCE);
if (get_local_id(0) == 0) {{
    int glid = get_group_id(0) * {len(llvm_instructions)};
    for (int i = glid; i < glid + {len(llvm_instructions)}; i++)
        {hidden_counter_name_global}[i] = {hidden_counter_name_local}[i - glid];
}}
'''

def add_instrumentation_data_to_file(filename, instr_data_raw):
    '''
    returns a dictionary "line (int): code to add (string)"
    '''

    from collections import defaultdict

    def write_incr(key, val):
        '''
        returns the instrumentation string
        '''
        return f'atomic_add(&{hidden_counter_name_local}[{key}], {val});'

    # parse instrumentation data and create an instrumentation dict
    instr_data_dict = defaultdict(str)
    for line in instr_data_raw.splitlines():
        bb_instrumentation_data = [0] * len(llvm_instructions)
        data = filter(None, line.split('|')[1:])
        for datum in data:
            [lineno, instruction] = datum.split(':')
            bb_instrumentation_data[llvm_instructions.index(instruction)] += 1
        for instruction_index, instruction_cnt in enumerate(bb_instrumentation_data):
            if instruction_cnt > 0:
                instr_data_dict[int(lineno)] += write_incr(instruction_index, instruction_cnt)

    # now modify the file in place with the instr_data dict
    # the instr_data is a dict <line:instrumentation_data>
    with open(filename, 'r') as f:
        filedata = f.readlines()
    offset = -1
    insertion_line = 0
    for lineno in instr_data_dict.keys():
        # must add instrumentation data between the previous line and this one
        insertion_line = lineno + offset
        filedata.insert(insertion_line, instr_data_dict[lineno] + '\n')
        offset += 1
    insertion_line += 1

    # lastly, add code at the end to copy local buffer to the respective space in the global one
    filedata.insert(insertion_line, epilogue)

    # done; write the instrumented source back to file
    with open(filename, 'w') as f:
        f.writelines(filedata)
