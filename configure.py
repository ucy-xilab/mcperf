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

def find_kernel_config(pstate, c1, c1e, c6):
    with open('kernel_configs.yml', 'r') as f:
        kcs = yaml.safe_load(f)
        for kc in kcs:
            target_config = {
                'pstate': pstate, 
                'c1': c1, 
                'c1e': c1e, 
                'c6': c6
            }
            if kc['target'] == target_config:
                return kc
    return None

def configure_grub(kc):
    common_boot_options = 'console=ttyS0,115200'
    extra_boot_options = kc['config']['boot_options']
    grub_cmdline_linux = 'GRUB_CMDLINE_LINUX="{} {}"'.format(common_boot_options, extra_boot_options)
    sed_inplace('/etc/default/grub', 'GRUB_CMDLINE_LINUX=\".*\"', grub_cmdline_linux)

def check_current_kernel_matches_target_kernel(kc):
    target_kernel_image = kc['config']['boot_options']
    uname = os.popen('uname -a').read().strip()
    if target_kernel_image not in uname:
        return False
    target_boot_options = kc['config']['boot_options']
    with open('/proc/cmdline', 'r') as fi:
        current_bootoptions = fi.readline()
        if target_boot_options not in current_bootoptions:
            return False
    return True

def main(argv):
    kc = find_kernel_config(False, '2-2', '10-20', True)
    if not kc:
        raise Exception("Target kernel configuration not known")
    if not check_current_kernel_matches_target_kernel(kc):
        configure_grub(kc)    

if __name__ == "__main__":
    main(sys.argv)