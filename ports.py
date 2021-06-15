
from dataclasses import dataclass
import socket
from pathlib import Path
import json
from multiprocessing.pool import ThreadPool
import datetime as dt
from configFileHelper import Config

try:
    from icecream import ic

    def ic_set(debug):
        if debug:
            ic.enable()
        else:
            ic.disable()


# Graceful fallback if IceCream isn't installed.
except (ImportError, FileNotFoundError):
    doDebug: bool = False

    def ic(thing):  # just print to STDOUT
        if doDebug:
            print(thing)

    def ic_set(debug):
        global doDebug
        doDebug = debug
        ic("* icecream module not imported successfully, using STDOUT")


THIS_PATH = Path(__file__).parent.resolve()


def nowString():
    return f"{dt.datetime.now().strftime('%Y.%m.%d %T')} |> "


try:
    ic.configureOutput(prefix=nowString)
except AttributeError:
    pass

CONFIG = Config(file_path=THIS_PATH.joinpath('config.yaml'))

ic_set(CONFIG.get_bool(['APP', 'DEBUG']))

ic(str(CONFIG))

PROTOCOLS = CONFIG.get('PROTOCOLS')


@dataclass
class port(object):

    _TESTING_IP = CONFIG.get(['PORTS', 'TESTING_IP'])

    Port: int
    Description: str
    Status: str = None
    if 'TCP' in PROTOCOLS:
        isTCP: bool = True
        TCPisOK: bool = None
    if 'UDP' in PROTOCOLS:
        isUDP: bool = False
        UDPisOK: bool = None

    def __init__(self, **kwargs):
        if 'row' in kwargs:
            theDict = kwargs.get('row')
            self = port.__init__(self, Port=theDict.get('Port'), Description=theDict.get('Description'), Status=theDict.get('Status', None), isTCP=theDict.get('isTCP', theDict.get('TCP', False)), isUDP=theDict.get('isUDP', theDict.get('UDP', False)), TCPisOK=theDict.get('TCPisOK', False), UDPisOK=theDict.get('UDPisOK', False)
                                 )
        else:
            self.Port = int(kwargs.get('Port'))
            self.Description = kwargs.get('Description')
            self.Status = kwargs.get('Status', None)
            if 'TCP' in PROTOCOLS:
                self.isTCP = kwargs.get('isTCP', True)
                self.TCPisOK = kwargs.get('TCPisOK', None)
            if 'UDP' in PROTOCOLS:
                self.isUDP = kwargs.get('isUDP', False)
                self.UDPisOK = kwargs.get('UDPisOK', None)

    def testThisPort(self, timeout: int = CONFIG.get(['PORTS', 'TIMEOUT_S'])):

        def tryIt(type):
            try:
                s = socket.socket(socket.AF_INET, type)
                s.settimeout(timeout)
                s.connect(CONN_TUPLE)
                answer = True
            except socket.timeout as e:
                answer = False
            finally:
                s.close()
            return answer

        CONN_TUPLE = (port. _TESTING_IP, self.Port)
        if 'TCP' in PROTOCOLS:
            if self.isTCP == True:
                self.TCPisOK = tryIt(socket.SOCK_STREAM)
            else:
                self.TCPisOK = None
        if 'UDP' in PROTOCOLS:
            if self.isUDP == True:
                self.UDPisOK = tryIt(socket.SOCK_DGRAM)
            else:
                self.UDPisOK = None

        return self


def readJSON(fname):
    theData = json.loads(fname.read_text())
    ic(f"{len(theData)} rows in input file")
    ports = [port(row=d) for d in theData if not (
        type(d["Port"]) == str and '-' in d["Port"])]
    for d in [d for d in theData if type(d["Port"]) == str and '-' in d["Port"]]:
        portRange = d["Port"].split('-')
        for p in range(int(portRange[0]), int(portRange[1])+1):
            d["Port"] = p
            ports.append(port(row=d))
        portRange = None
    theData = None
    return ports


def writeJSON(ports, fname):
    fname.write_text(json.dumps([p.__dict__ for p in ports], indent=2))


def testPort(port):
    return port.testThisPort()


def go():

    paths = {'INPUT': CONFIG.get(['FILES', 'INPUT']), 'OUTPUT': CONFIG.get(['FILES', 'OUTPUT'])
             }

    openTemplate = CONFIG.get(['FILES', 'OPEN'])  # s ports.open.%PROTO%.json
    for p in PROTOCOLS:
        paths[p] = openTemplate.replace('%PROTO%', p)

    for k in paths.keys():
        if type(paths[k]) == str:
            paths[k] = THIS_PATH.joinpath(paths[k])

    ic('Testing : ', PROTOCOLS)
    ic(paths)

    ports = readJSON(paths['INPUT'])
    ic(f"{len(ports)} for testing")

    # ports = ports[0:444]
    numThreads, updateInterval, cnt, padl = int(CONFIG.get(['APP', 'NUM_THREADS'])), int(CONFIG.get(
        ['APP', 'FEEDBACK_INTERVAL'])), 0, len(str(len(ports)))

    testedPorts, tested = [], ThreadPool(
        numThreads).imap_unordered(testPort, ports)

    def feedback(c):
        ic(str(c).rjust(padl))
        sortedPorts = [p for p in sorted(testedPorts, key=lambda k: k.Port)]
        writeJSON(sortedPorts, paths['OUTPUT'])
        for p in PROTOCOLS:
            writeJSON([t for t in sortedPorts if t.__dict__[
                f"{p}isOK"] == True], paths[p])
    feedback(0)
    for p in tested:
        testedPorts.append(p)
        cnt += 1
        if (cnt % updateInterval) == 0:
            feedback(c=cnt)
    feedback(cnt)
    testedPorts = None

# def rejig():
#     input = Path(THIS_PATH.joinpath(CONFIG.get(['FILES', 'INPUT'])))
#     ic(input)
#     ports = readJSON(input)

#     def lookup(port_):
#         matches = [p for p in ports if p.Port == port_]
#         # if len(matches) > 1:
#         #     ic(port_, len(matches))
#         this = port(Port=port_, Description="", Status=""
#                     )
#         this.Description = '; '.join(
#             list(set([m.Description for m in matches])))
#         try:
#             if len(list(set([m.Status for m in matches]))) == 1:
#                 this.Status = matches[0].Status
#         except Exception as e:
#             print(this)
#             print(matches)
#             raise e
#         this.isTCP = False
#         this.isUDP = True
#         for m in matches:
#             if not (m.isTCP == None or m.isTCP == False):
#                 this.isTCP = True
#             if not (m.isUDP == None or m.isUDP == False):
#                 this.isUDP = True
#         return this
#     ic(len(ports))
#     distinct = list(set([p.Port for p in ports]))
#     ic(len(distinct))
#     newPorts = [lookup(p) for p in distinct]
#     writeJSON(newPorts, Path(CONFIG.get(['FILES', 'INPUT'])))


# def checkit():
#     ports = readJSON(Path(THIS_PATH.joinpath(CONFIG.get(['FILES', 'INPUT']))))
#     neither = [p for p in ports if not (p.isTCP == True or p.isUDP == True)]
#     TCP = [p for p in ports if p.isTCP == True]
#     UDP = [p for p in ports if p.isUDP == True]
#     ic(len(ports), len(neither), len(TCP), len(UDP))


if __name__ == '__main__':
    # checkit()
    go()
