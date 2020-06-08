import argparse
import os
import oclude.utils as utils

# define the arguments of oclude
parser = argparse.ArgumentParser(
    description='oclude - the OpenCL universal driving environment'
)

parser.add_argument('infile',
    type=str,
    help='the *.cl file with the OpenCL kernel(s)'
)

parser.add_argument('-k', '--kernel',
    type=str,
    help='the name of the kernel to run from the input file'
)

parser.add_argument('-g', '--gsize',
    type=int,
    help='The global NDRange, i.e. the size of the buffer arguments of the kernel',
    required=True
)

parser.add_argument('-l', '--lsize',
    type=int,
    help='The local NDRange, i.e. the number of work items in a work group',
    required=True
)

parser.add_argument('-p', '--platform',
    type=int,
    help='the index of the OpenCL platform to use (default: 0)',
    default=0
)

parser.add_argument('-d', '--device',
    type=int,
    help='the index of the OpenCL device to use (default: 0)',
    default=0
)

parser.add_argument('-s', '--samples',
    type=int,
    help='number of times to execute the given kernel (note that each execution is initialized with different values)',
    default=1
)

parser.add_argument('-v', '--verbose',
    help='toggle verbose output (default: false)',
    action='store_true'
)

parser.add_argument('-i', '--inst-counts',
    help='count the LLVM instructions that were executed and dump them to stdout',
    dest='instcounts',
    action='store_true'
)

parser.add_argument('-t', '--time-it',
    help='measure kernel execution time and dump it to stdout',
    dest='timeit',
    action='store_true'
)

parser.add_argument('--device-profiling',
    help='get profiling info regarding the selected OpenCL device',
    dest='device_profiling',
    action='store_true'
)

# cache flags #
parser.add_argument('--clear-cache',
    help='remove every cached info (irreversible)',
    dest='clear_cache',
    action='store_true'
)

parser.add_argument('--ignore-cache',
    help='do not use (possibly) cached info regarding the provided kernel file',
    dest='ignore_cache',
    action='store_true'
)

parser.add_argument('--no-cache-warnings',
    help='suppress cache-related warnings (e.g. cache too large)',
    dest='no_cache_warnings',
    action='store_true'
)

###############################
### MAIN FUNCTION OF OCLUDE ###
###############################
def run():

    args = parser.parse_args()

    interact = utils.Interactor(__file__.split(os.sep)[-1])
    interact.set_verbosity(args.verbose)

    # some sanity checks
    if not os.path.exists(args.infile):
        interact(f'ERROR: Input file {args.infile} does not exist.')
        exit(1)

    if args.instcounts and args.timeit:
        interact('WARNING: Instruction count and execution time measurement were both requested.')
        interact('This will result in the time measurement of the instrumented kernel and not the original.')
        interact('Proceed? [y/N] ', nl=False)
        if input() != 'y':
            exit(0)

    ### STEP 1: cache checking (if needed) ###
    ##########################################
    #   1. was any of the flags below used?
    #       instcounts: Is the instrumented version of the file cached?
    #           YES: use it
    #           NO: go on to instrumentation, remember to cache it when done
    #       timeit: No need to do something
    #   2. check if cache knows the file kernels (this whole step should be done transparently, inside cache class)
    #       YES: get them and:
    #           a. user specified a kernel: check if it exists in the file (could fail)
    #           b. user did not specify a kernel: prompt them
    #       NO: find them, and go to YES
    ##########################################

    cache = utils.CachedFiles()

    if cache.size > 10 * 1024 * 1024 and not args.no_cache_warnings:
        interact('WARNING: Cache size exceeds 10 MiB, which is a lot. Consider running oclude with `--clear-cache`')

    if args.clear_cache:
        interact('INFO: Clearing cache')
        cache.clear()

    is_cached = False
    if args.ignore_cache:
        interact('INFO: Ignoring cache')
    else:
        is_cached = cache.file_is_cached(args.infile)
        interact(f"INFO: Input file {args.infile} is {'' if is_cached else 'not '}cached")

    # step 1.1
    if args.instcounts:
        infile = cache.get_name_of_instrumented_file(args.infile)
        if is_cached and not args.ignore_cache:
            interact('INFO: Using cached instrumented file')
        else:
            interact('Instrumenting source file')
            cache.copy_file_to_cache(args.infile)
            utils.instrument_file(infile, args.verbose)
    else:
        infile = args.infile
        if not is_cached:
            cache.copy_file_to_cache(infile)

    # step 1.2
    file_kernels = cache.get_file_kernels(args.infile)
    if not args.kernel or args.kernel not in file_kernels:
        if args.kernel:
            interact(f"ERROR: No kernel function named '{args.kernel}' exists in file '{args.infile}'")
        interact(f"A list of the kernels that exist in file '{args.infile}':")
        for i, kernel in enumerate(file_kernels, 1):
            interact(f'\t{i}. {kernel}')
        # input file contains only one kernel
        if len(file_kernels) == 1:
            interact('Do you want to run the above kernel? [Y/n] ', nl=False)
            if input() == 'n':
                exit(0)
            else:
                inp = 0
        # input file contains > 1 kernels
        else:
            interact('Do you want to run one of the above? If yes, type the number on its left. If no, just hit <Enter>: ', nl=False)
            inp = input()
            if not inp:
                exit(0)
            else:
                inp = int(inp) - 1
                if not 0 <= inp < len(file_kernels):
                    interact(f'Should have chosen between 1 and {len(file_kernels)}. Please try again')
                    exit(1)
        args.kernel = file_kernels[inp]
        interact(f"Continuing with kernel '{args.kernel}'")

    ### STEP 2: run the kernel ###
    interact(f'Running kernel {args.kernel} from file {args.infile}')
    results = utils.run_kernel(
        infile, args.kernel,
        args.gsize, args.lsize,
        args.samples,
        args.platform, args.device,
        args.instcounts, args.timeit, args.device_profiling,
        args.verbose
    )

    ### STEP 3: dump an oclgrind-like output (if requested by user) ###
    if args.instcounts:
        print(f"Instructions executed for kernel '{args.kernel}':")
        for instname, instcount in sorted(results['instcounts'].items(), key=lambda item : item[1], reverse=True):
            if instcount != 0:
                print(f'{instcount:16} - {instname}')

    if args.timeit:
        kernel_results = results['timeit']
        indent = max(len(timing_scope) for timing_scope in kernel_results.keys())
        print(f"Time measurement info regarding the execution for kernel '{args.kernel}' (in milliseconds):")
        for timing_scope, time_elapsed in kernel_results.items():
            print(f'{timing_scope:>{indent}} - {time_elapsed}')

    if args.device_profiling:
        device_prof_results = results['device_profiling']
        indent = max(len(profiling_category) for profiling_category in device_prof_results.keys())
        print('Profiling info for selected OpenCL device:')
        for profiling_category, time_info in device_prof_results.items():
            print(f'{profiling_category:>{indent}} - {time_info}')
