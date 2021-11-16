import sys
import yaml

#def config_matches(kernel_config, target_config):


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

def configure_kernel(kc):
    print(kc['config'])

def main(argv):
    kc = find_kernel_config(False, '2-2', '10-20', True)
    if not kc:
        raise Exception("Target kernel configuration not known")
    configure_kernel(kc)    

if __name__ == "__main__":
    main(sys.argv)