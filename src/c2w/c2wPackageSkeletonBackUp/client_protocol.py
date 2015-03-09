import sys
import struct
from ctypes import create_string_buffer

try:
    from twisted.internet.protocol import Protocol
except:
    print "IMPORT_ERROR: Unable to import twisted module"
    sys.exit(1)


class BinChatClientProtocol(Protocol):

    def __init__(self):
        # initialization stuff
        pass

    def dataReceived(self, data):

        # You must implement a framing protocol before decoding a c2w message
        # Of course, you will remove the pass instruction !
        pass
