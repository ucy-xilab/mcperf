class Configuration:
    def __init__(self, adict):
        self.__dict__.update(adict)
    def set(self, key, value):
        self.__dict__[key] = value
    def shortname(self):
        l = []
        l.append("qps={}".format(self.mcperf_qps))
        return '-'.join(l)
