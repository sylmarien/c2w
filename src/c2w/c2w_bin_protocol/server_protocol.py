# -*- coding: utf-8 -*-

from twisted.internet.protocol import Protocol, Factory
from c2w_main.chat_server_protocol_factory import ChatServerProtocolFactory
from twisted.internet import reactor
import struct
from ctypes import create_string_buffer
from c2w_main.user import User, UserList
from c2w_main.movie import Movie, MovieList
import ctypes
import twisted.internet.protocol
import sys

class BinChatServerProtocol(Protocol):

    listId = [1 for i in range(0,64)] #chaque case indique si le userId est pris : 1 <=> libre, 0 <=> utilisé

    def __init__(self, users, movies, factory):

        # initialization stuff
        self.users = users
        self.movies = movies
        self.factory = factory
        self.buffer = ''
        self.lengthReceived = 0
        self.packSize = 0
        self.currentId = 0
        self.name = ''
        self.room = ''
        self.seqNum = 0
        self.ackNum = 0


    def dataReceived(self, data):

        size = len(data)
        self.lengthReceived += size
        self.buffer += data

        if (self.lengthReceived >= 2 and self.packSize == 0): #si on a recu plus de 2 octets, on calcule la longueur du packet
            (self.packSize, ) = struct.unpack('<H', self.buffer[:2])

        if (self.lengthReceived >= self.packSize and self.packSize > 0): #Si on a recu plus d'octets que la longueur du packet, dans le cas ou celle-ci est deja connue, on trie et analyse les donnees contenues dans le packet
            msgTyp, seqNum, srcUID, dstUID, ackBit, ackNum, options, content = self.readPacket(self.buffer)
            self.buffer = self.buffer[self.packSize:]
            self.lengthReceived = self.lengthReceived % self.packSize
            self.packSize = 0 #on retire du buffer ce qui vient d'être analysé
            self.processPacket(msgTyp, seqNum, srcUID, dstUID, ackBit, ackNum, options, content) #on traite le packet : méthode à faire
    

    #on va "décortiquer" le paquet reçu
    def readPacket(self, data):
        #on extrait les champs de l'entête par octet puis on séparre bien chacune des informations
        (msgLen, msgTypANDseqNum, srcUID, dstUID, ackBitANDackNumANDres, totOptLen, ), content = struct.unpack('<HBBBBH', data[:8]), data[8:]
        msgTyp = (msgTypANDseqNum & 0b11110000) >> 4
        seqNum = (msgTypANDseqNum & 0b00001111)
        ackBit = (ackBitANDackNumANDres & 0b10000000) >> 7
        ackNum = (ackBitANDackNumANDres & 0b01111000) >> 3
        
        optLenViewed = 0
        options = []
        # on remplit la liste des options par les options contenues dans le paquet
        while optLenViewed < totOptLen:
            (optLen, optTypeAndLastF, ) = struct.unpack('<BB', content[optLenViewed:optLenViewed+2])
            optType = (optTypeAndLastF & 0b11110000) >> 4
            if optType == 0b0:
                (optId, optContent, ) = struct.unpack('<B%ds' %(optLen-3), content[optLenViewed+2:optLenViewed+optLen])
                options.append([optType, optId, optContent])
            elif optType == 0b1:
                (optPort,) = struct.unpack('<H', content[optLenViewed+2:optLenViewed+optLen])
                options.append([optType, optPort])
            elif optType == 0b10:
                (optUID, optRID, ) = struct.unpack('<BB', content[optLenViewed+2:optLenViewed+optLen])
                options.append([optType, optUID, optRID])
            optLenViewed += optLen

        # on remplit fContent, pour finalContent, avec le contenu du champ data du paquet
        fContent = struct.unpack('%ds' % (msgLen-(8+totOptLen)), content[totOptLen:])

        #on renvoie toutes les infos utiles (et plus ce qui ne sert plus, comme le "last flag" des options)
        return msgTyp, seqNum, srcUID, dstUID, ackBit, ackNum, options, fContent


    #à part options et data, toutes les variables sont des nombres (on peut les écrire en hexa, en binaire ou en décimale, peut importe)
    #options est une liste d'options, chacun de ses éléments est une liste dont le nombre d'éléments dépend du type de l'option (cf spécification et readPacket)
    #data est une chaîne de caractère
    #NB : on n'est pas obligé de renseigner options et data quand on appelle cette fonction : s'ils ne sont pas renseignés, par défaut la fonction va leur donner, respectivement, les valeurs [] et ''
    def sendPacket(self, msgTyp, seqNum, srcUID, dstUID, ackBit, ackNum, options = [], data = ''):
        #on rassemble les informations de telle façon qu'elles soient codées sur des octets complets
        msgTypANDseqNum = (msgTyp << 4) + seqNum
        ackField = (ackBit << 7) + (ackNum << 3)
        
        #on va extraire de la liste d'options toutes les informations de façon à pouvoir les mettre dans le paquet
        #on utilise l'objet iterator de python, il va nous permettre de savoir quand on arrive sur la dernière option
        optionMsg = ''
        if options != []:
            iterator = options.__iter__()
            next = options.__iter__()
            nextOpt = next.next()

            #la suite de ce code sert encoder le champ option, la dernière option prendra le "last flag" à 1
            while True:
                try:
                    nextOpt = next.next() #si on est sur la dernière option, cette ligne va lever l'exception StopIteration et on va donc passer dans la partie except du code et donc mettre le last flaf à 1
                    option = iterator.next()
                    optLen = 3
                    if option[0] == 0b0:
                        contLen = len(option[2])
                        optLen += contLen
                        optType = (option[0] << 4)
                        optionMsg += struct.pack('<BBB%ds' % contLen, optLen, optType, option[1], option[2])
                    if option[0] == 0b1:
                        optLen += 1
                        optType = (option[0] << 4)
                        optionMsg += struct.pack('<BBH', optLen, optType, option[1])  
                    if option[0] == 0b10:
                        optLen += 1
                        optType = (option[0] << 4)
                        optionMsg += struct.pack('<BBBB', optLen, optType, option[1], option[2])
                except StopIteration:
                    option = iterator.next()
                    optLen = 3
                    if option[0] == 0b0:
                        contLen = len(option[2])
                        optLen += contLen
                        optTypeAndLastF = (option[0] << 4) + (0b1 << 3)
                        optionMsg += struct.pack('<BBB%ds' % contLen, optLen, optTypeAndLastF, option[1], option[2])
                    if option[0] == 0b1:
                        optLen += 1
                        optTypeAndLastF = (option[0] << 4) + (0b1 << 3)
                        optionMsg += struct.pack('<BBH', optLen, optTypeAndLastF, option[1])  
                    if option[0] == 0b10:
                        optLen += 1
                        optTypeAndLastF = (option[0] << 4) + (0b1 << 3)
                        optionMsg += struct.pack('<BBBB', optLen, optTypeAndLastF, option[1], option[2])
                    break
        #on a maintenant la possibilité de calculer la longueur totale du champ options du paquet puis celle du paquet complet.
        totOptLen = len(optionMsg)
        msgLen = 8 + totOptLen + len(data)

        #On remplit le paquet avec l'entête et les options
        message = struct.pack('<HBBBBH', msgLen, msgTypANDseqNum, srcUID, dstUID, ackField, totOptLen) + optionMsg
        
        #on met les données dans le paquet
        message += struct.pack('<%ds' %len(data), data)

        #on envoie le tout à l'utilisateur
        self.transport.write(message)


    def getNewUserId(self):
        #on trouve le premier ID non utilisé et on le renvoie. S'il n'y a pas d'ID libre, on quitte (pas de gestion des erreurs à implémenter)
        pos = 0
        while pos < 64:
            if BinChatServerProtocol.listId[pos] == 1:
                BinChatServerProtocol.listId[pos] = 0
                self.currentId = (0b10 << 6) + pos
                return self.currentId
            else:
                pos += 1
        sys.exit()


    def processPacket(self, msgTyp, seqNum, srcUID, dstUID, ackBit, ackNum, options, content):

        if self.ackNum == seqNum:

            if (msgTyp == 0b0): #demande de login
                self.processLogin(options[0][2])

            elif (msgTyp == 0b1):#demande de userList
                self.processUserList()

            elif (msgTyp == 0b11):#demande de movieList
                self.processMovieList()

            elif (msgTyp == 0b101):#demande pour rejoindre une movie room
                self.processJoinMovie(options)

            elif (msgTyp == 0b1001):#demande pour quitter la room actuelle
                self.processLeaveRequest()

            elif (msgTyp == 0b1011):#chat message => rediffuser à tout le monde et acquitter à l'émetteur
                self.processChatMessage(content)

            else:
                pass
            

    def processLogin(self, name):

        self.ackNum += 1

        if self.factory.users.userExist(name): #on teste si le username est deja pris, si oui, on passe (pas de gestion des erreurs à implémenter)
            pass
        else:
            self.sendPacket(0b111, self.seqNum, 0b11111111, self.getNewUserId(), 1, self.ackNum) #positive resonse
            self.factory.users.createAndAddUser(name, 'MainRoom', self.currentId, self) #ajout de l'utilisateur à la liste des users
            #on "dit" à tous les utilisateurs que le nouvel user est arrivé
            for luser in self.factory.users.getAllUsersList():
                if luser.chatInstance != self:
                    luser.chatInstance.sendPacket(0b1010, self.seqNum, 0b11111111, luser.id, 0, self.ackNum, [[0,self.currentId, name],[0, self.currentId, 'MainRoom']])
            
            self.name = name
            self.seqNum += 1


    def processUserList(self):

        self.ackNum += 1

        listOfUsers = self.factory.users.getAllUsersList()
        formatedOption = []

        #on remplit les options selon le bon formatage
        for luser in sorted(listOfUsers, key=lambda user: user.id):
            tmpOpt1 = []
            tmpOpt1.append(0b0)
            tmpOpt1.append(luser.id)
            tmpOpt1.append(luser.name)
            tmpOpt2 = []
            tmpOpt2.append(0b0)
            tmpOpt2.append(luser.id)
            tmpOpt2.append(luser.chatRoom)

            formatedOption.append(tmpOpt1)
            formatedOption.append(tmpOpt2)

        #on envoie la userList
        self.sendPacket(0b0010, self.seqNum, 0b11111111, self.currentId, 1, self.ackNum, formatedOption)
        self.seqNum += 1


    def processMovieList(self):

        self.ackNum += 1

        listOfMovies = self.factory.movies.getMoviesList()
        formatedOption = []

        #on remplit les options selon le bon formatage
        for lmovie in listOfMovies:
            tmpOpt1 = []
            tmpOpt1.append(0b0)
            if lmovie.id != None:
                tmpOpt1.append(lmovie.id)
            else:
                tmpOpt1.append(0b01000000)
            tmpOpt1.append(lmovie.title)
            tmpOpt2 = []
            tmpOpt2.append(0b1)
            tmpOpt2.append(lmovie.port)
            formatedOption.append(tmpOpt1)
            formatedOption.append(tmpOpt2)

        #on envoie la movieList
        self.sendPacket(0b100, self.seqNum, 0b11111111, self.currentId, 1, self.ackNum, formatedOption)
        self.seqNum += 1


    def processLeaveRequest(self):

        self.ackNum += 1
        #on parcourt l'ensemble des utilisateurs connectés
        for luser in self.factory.users.getAllUsersList():
            #si c'est l'utilisateur courant, on lui "dit" qu'il peut quitter la room actuelle (s'il est dans la main room, il se déconnecte)
            if luser.name == self.name:
                self.sendPacket(0b1010, self.seqNum, 0b11111111, self.currentId, 1, self.ackNum, [[0, self.currentId, self.name],[2, self.currentId, -1]])
                self.seqNum += 1
            #sinon on prévient l'utilisateur que l'utilisateur courant change de room (ou quitte le serveur)
            else:
                #si l'utilisateur était dans la main room, il se déconnecte
                if self.room == 'MainRoom':
                    luser.chatInstance.sendPacket(0b1010, luser.chatInstance.seqNum, 0b11111111, luser.id, 0, luser.chatInstance.ackNum, [[0, self.currentId, self.name],[2, self.currentId, -1]])
                    luser.chatInstance.seqNum += 1
                #sinon, il va dans la main room
                else:
                    luser.chatInstance.sendPacket(0b1010, luser.chatInstance.seqNum, 0b11111111, luser.id, 0, luser.chatInstance.ackNum, [[0, self.currentId, self.name],[0, self.currentId, 'MainRoom']])
                    luser.chatInstance.seqNum += 1
        #si l'utilisateur était dans la main room, il vient donc de se déconnecter, on agit en conséquence :
        if self.room == 'MainRoom':
            #on supprime l'utilisateur de la liste des utilisateurs connectés
            self.factory.users.removeUser(self.name)
            #on ferme le processus qui s'occupait de lui
            sys.exit()
        #sinon, il ne se déconnecte pas, il va dans la mainRoom
        else:
            self.factory.users.updateUserChatRoom(self.name, 'MainRoom')


    def processJoinMovie(self, options):

        self.ackNum += 1
        #on change sa movie room dans la liste des utilisateurs connectés
        self.factory.users.updateUserChatRoom(self.name, options[0][2])
        self.room = options[0][2]
        #on parcourt l'ensemble des utilisateurs connectés
        for luser in self.factory.users.getAllUsersList():
            #si c'est l'utilisateur courant, on lui confirme son changement de movie room
            if luser.name == self.name:
                self.sendPacket(0b1010, self.seqNum, 0b11111111, self.currentId, 1, self.ackNum, [[0, self.currentId, self.name],[0, self.currentId, options[0][2]]])
                self.seqNum += 1
            #sinon on prévient l'utilisateur du changement de movie room de l'utilisateur courant
            else:
                luser.chatInstance.sendPacket(0b1010, luser.chatInstance.seqNum, 0b11111111, luser.id, 0, luser.chatInstance.ackNum, [[0, self.currentId, self.name],[0, self.currentId, options[0][2]]])
                luser.chatInstance.seqNum += 1


    def processChatMessage(self, message):

        self.ackNum += 1
        #on parcourt l'ensemble des utilisateurs connectés
        for luser in self.factory.users.getAllUsersList():
            #si c'est l'utilisateur courant, on acquitte la bonne réception de son message
            if luser.name == self.name:
                self.sendPacket(0b1100, self.seqNum, 0b11111111, self.currentId, 1, self.ackNum)
                self.seqNum += 1
            #sinon, on leur transmet le message avec en option le nom de l'émetteur aux utilisateurs qui sont dans la même room
            else:
                if luser.chatRoom == self.room:
                    luser.chatInstance.sendPacket(0b1011, luser.chatInstance.seqNum, 0b11111111, luser.id, 0, luser.chatInstance.ackNum, [[0, self.currentId, self.name]], message)
                    luser.chatInstance.seqNum += 1