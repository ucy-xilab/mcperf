import argparse
import distutils.util
import logging 
import os
import re
import sys
import shutil
import tempfile
import yaml

def sed_inplace(filename, pattern, repl, backup=False):
    '''
    Perform the pure-Python equivalent of in-place `sed` substitution: e.g.,
    `sed -i -e 's/'${pattern}'/'${repl}' "${filename}"`.
    '''
    # For efficiency, precompile the passed regular expression.
    pattern_compiled = re.compile(pattern)

    # For portability, NamedTemporaryFile() defaults to mode "w+b" (i.e., binary
    # writing with updating). This is usually a good thing. In this case,
    # however, binary writing imposes non-trivial encoding constraints trivially
    # resolved by switching to text writing. Let's do that.
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
        with open(filename) as src_file:
            for line in src_file:
                tmp_file.write(pattern_compiled.sub(repl, line))
    # Create a backup of the original file
    if backup:
        backup_filename = os.path.join(filename, '.old')
        shutil.copy(filename, backup_filename)

    # Overwrite the original file with the munged temporary file in a
    # manner preserving file attributes (e.g., permissions).
    shutil.copystat(filename, tmp_file.name)
    shutil.move(tmp_file.name, filename)

def load_kernel_configs():
    with open('kernel_configs.yml', 'r') as f:
        kcs = yaml.safe_load(f)
        return kcs

def find_kernel_config_using_name(kernel_configs, name):
    for kc in kernel_configs:
        if kc['name'] == name:
            return kc
    return None 

def find_kernel_config_using_parameters(kernel_configs, pstate, c1, c1e, c6):
    for kc in kernel_configs:
        target_config = {
            'pstate': pstate, 
            'c1': c1, 
            'c1e': c1e, 
            'c6': c6
        }
        if kc['config'] == target_config:
            return kc
    return None

def find_kernel_config_using_current_kernel(kernel_configs):
    kernel_uname = os.popen('uname -a').read().strip()
    with open('/proc/cmdline', 'r') as fi:
        kernel_bootoptions = fi.readline().strip()
    common_boot_options = 'console=ttyS0,115200'
    for kc in kernel_configs:
        expected_boot_options = kc['grub']['boot_options']
        if len(expected_boot_options) > 0:
            expected_boot_options = common_boot_options + ' ' + expected_boot_options 
        else:
            expected_boot_options = common_boot_options
        if kc['kernel'] in kernel_uname and kernel_bootoptions.endswith(expected_boot_options):
            return kc
    return None                

def check_kernel_(kc):
    target_kernel_image = kc['kernel']
    uname = os.popen('uname -a').read().strip()
    if target_kernel_image not in uname:
        return False
    target_boot_options = kc['grub']['boot_options']
    with open('/proc/cmdline', 'r') as fi:
        current_bootoptions = fi.readline()
        if target_boot_options not in current_bootoptions:
            return False
    return True

def configure_grub(kc):
    logging.info('Configure grub')
    grub_default = 'GRUB_DEFAULT="{}"'.format(kc['grub']['menuentry'])
    logging.info('Set {}'.format(grub_default))
    sed_inplace('/etc/default/grub', 'GRUB_DEFAULT=.*', grub_default)
    
    common_boot_options = 'console=ttyS0,115200'
    extra_boot_options = kc['grub']['boot_options']
    grub_cmdline_linux = 'GRUB_CMDLINE_LINUX="{} {}"'.format(common_boot_options, extra_boot_options)
    logging.info('Set {}'.format(grub_cmdline_linux))
    sed_inplace('/etc/default/grub', 'GRUB_CMDLINE_LINUX=\".*\"', grub_cmdline_linux)

    os.system('update-grub2')

def configure_turbo(turbo):
    logging.info('Configure turbo boost')
    os.system('modprobe msr')
    if turbo:
        os.system('./turbo-boost.sh enable')
    else:
        os.system('./turbo-boost.sh disable')

def configure_pstate(pstate):
    logging.info('Configure pstate')
    if not pstate:
        os.system('LD_LIBRARY_PATH="/mydata/linux-4.15.18/" /mydata/linux-4.15.18/cpupower frequency-set -g performance')
        os.system('LD_LIBRARY_PATH="/mydata/linux-4.15.18/" /mydata/linux-4.15.18/cpupower frequency-set -d 2200MHz')
    else:
        os.system('LD_LIBRARY_PATH="/mydata/linux-4.15.18/" /mydata/linux-4.15.18/cpupower frequency-set -g powersave')
    os.system('LD_LIBRARY_PATH="/mydata/linux-4.15.18/" /mydata/linux-4.15.18/cpupower frequency-info')

def parse_args():
    """Configures and parses command-line arguments"""
    parser = argparse.ArgumentParser(
                    prog = 'configure',
                    description='configure kernel',
                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-n", "--node", dest='node', help="node to configure")

    parser.add_argument("--turbo", dest='turbo', default=True, help="turbo")
    parser.add_argument("--kernelconfig", dest='kernelconfig', help="kernel configuration name")
    parser.add_argument("--pstate", dest='pstate', help="p state")
    parser.add_argument("--c1", dest='c1', help="c1 state")
    parser.add_argument("--c1e", dest='c1e', help="c1e state")
    parser.add_argument("--c6", dest='c6', help="c6 state")
    parser.add_argument(
        "-v", "--verbose", dest='verbose', action='store_true',
        help="verbose")

    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s')

    if args.verbose:
        logging.getLogger('').setLevel(logging.INFO)
    else:
        logging.getLogger('').setLevel(logging.ERROR)

    return args

def log_kernel_configuration(kc):
    logging.info('  name: {}'.format(kc['name']))
    logging.info('  config: {}'.format(kc['config']))

def main():
    args = parse_args()

    if os.geteuid() != 0:
        logging.error('You need root permissions to do this')
        return

    kcs = load_kernel_configs()
    
    if args.kernelconfig:
        target_kc = find_kernel_config_using_name(kcs, args.kernelconfig)
    else:
        target_kc = find_kernel_config_using_parameters(kcs, args.pstate, args.c1, args.c1e, args.c6)
    if not target_kc:
        logging.error("Target kernel configuration not known")
        return
    logging.info('Target kernel configuration')
    log_kernel_configuration(target_kc)

    current_kc = find_kernel_config_using_current_kernel(kcs)
    if current_kc:
        logging.info('Current kernel configuration')
        log_kernel_configuration(current_kc)
    else:    
        logging.info('Current kernel configuration is not known')

    if not current_kc or current_kc['name'] != target_kc['name']:
        configure_grub(target_kc)    
        logging.info('Reboot machine and rerun configure to finish configuration')
        sys.exit(2)

    configure_turbo(distutils.util.strtobool(args.turbo))
    # Yanos said we can keep the default governor
    #configure_pstate(target_kc['config']['pstate'])

if __name__ == "__main__":
    main()
