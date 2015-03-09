from twisted.internet.protocol import Protocol, Factory
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor
import struct
from ctypes import create_string_buffer
from c2w_main.user import User, UserList
from c2w_main.movie import Movie, MovieList


class BinChatServerProtocol(Protocol):

    lastUserId = 0b10000000

    def __init__(self, users, movies, factory):

        # initialization stuff
        self.users = users
        self.movies = movies
        self.factory = factory

    def dataReceived(self, data):
        self.transport.write(data)
        # You must implement a framing protocol before decoding a c2w message
        # Of course, you will remove the pass instruction !
        
