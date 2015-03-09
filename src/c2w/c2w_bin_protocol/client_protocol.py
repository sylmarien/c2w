# -*- coding: utf-8 -*-

import sys
import struct
from ctypes import create_string_buffer
import c2w_main.c2w_constants

try:
    from twisted.internet.protocol import Protocol
except:
    print "IMPORT_ERROR: Unable to import twisted module"
    sys.exit(1)


class BinChatClientProtocol(Protocol):

    def __init__(self):
        # initialization stuff
        self.chatClientProtocolController = None
        self.buffer = ''
        self.lengthReceived = 0
        self.packSize = 0
        self.seqNum = 0
        self.ackNum = 0
        self.userId = 0
        self.userName = ''
        self.tempName = ''
        self.tempMovie = ''
        self.tempMovieLocations = []


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


    def processPacket(self, msgTyp, seqNum, srcUID, dstUID, ackBit, ackNum, options, content):

        if self.ackNum == seqNum:

            if (msgTyp == 0b10): #réponse à une demande de userList
                self.processUserList(options)
                
            elif (msgTyp == 0b100):#réponse à une demande de movieList
                self.processMovieList(options)

            elif (msgTyp == 0b111):#positive response : utilisé uniquement pour confirmer la connexion
                self.setLogin(dstUID)

            elif (msgTyp == 0b1010):#user status update
                self.userStatusUpdate(options)

            elif (msgTyp == 0b1011):#chat message
                self.receivedChatMessage(options[0][2], content)

            else:
                pass


    def sendLogin(self, name):

        #envoi au serveur de la demande de login et enregistrement du nom de l'utilisateur pour un usage futur
        self.sendPacket(0b0, self.seqNum, 0, 0b11111111, 0, self.ackNum, [[0, 0, name]])
        self.userName = name
        self.seqNum += 1


    def setLogin(self, dstUID):

        #la connexion est ouverte, on "prévient" l'interface graphique que l'utilisateur est connecté avec son username
        self.chatClientProtocolController.setThisUserName(self.userName)
        #on retient le user ID donné par le serveur, il servira pour chaque envoi de paquet
        self.userId = dstUID


    def sendAskUserList(self):

        #on envoie au serveur la demande de userlist
        self.sendPacket(0b1, self.seqNum, self.userId, 0b11111111, 0, self.ackNum)
        self.seqNum += 1


    def processUserList(self, options):

        userList = []
        #on va profiter du fait que l'on connait comment sont construits les paquets par le serveur, tmp sert à savoir quel type d'information sera à récupérer dans le paquet :
        #tmp = 0 implique que le paquet contient le nom d'un utilisateur
        #tmp = 1 implique que le paquet contient la room dans laquelle est l'utilisateur dont on a récupéré le nom juste avant
        tmp = 0

        #pour contourner le fait que l'on ne connait pas encore les movies, on dit que tous les utilisateurs sont dans la main room pour commencer, cela sera mis à jour dès qu'on obtiendra la movielist
        for elt in options:
            if tmp == 0:
                self.tempName = elt[2]
                userList.append((self.tempName, c2w_constants.ROOM_IDS.MAIN_ROOM))
                tmp = 1
            if tmp == 1:
                #si l'utilisateur est effectivement dans la main room, on doit utiliser la constante définies par les professeurs
                if elt[2] == 'MainRoom':
                    self.tempMovieLocations.append([self.tempName,c2w_constants.ROOM_IDS.MAIN_ROOM])
                else:
                    self.tempMovieLocations.append([self.tempName, elt[2]])
                tmp = 0

        #on envoie au controller la liste (temporaire) des utilisateurs pour qu'elle soit affiché par l'interface graphique notamment
        self.chatClientProtocolController.setUserList(userList)


    def sendAskMovieList(self):

        #on envoie au serveur la demande de movielist
        self.sendPacket(0b11, self.seqNum, self.userId, 0b11111111, 0, self.ackNum)
        self.seqNum += 1


    def processMovieList(self, options):

        movieList = []

        #on utilise encore une fois notre connaissance de la construction des paquets : après avoir récupéré le nom d'une movie, on sait que l'option suivant contient le numéro de port associé à cette movie
        for elt in options:
            if elt[0] == 0:
                self.tempMovie = elt[2]
            if elt[0] == 1:
                movieList.append((self.tempMovie, elt[1]))

        #on envoie au controller la liste des movies pour qu'elle soit affichée par l'interface graphique notamment, mais également pour qu'il puisse ensuite recevoir les vidéos (il saura sur quel port "écouter")
        self.chatClientProtocolController.setMovieList(movieList)

        #ensuite, maintenant qu'on a toutes les movies, on met à jour les utilisateurs avec leur position réelle que l'on avait enregistrée précédemment
        for elt in self.tempMovieLocations:
            self.chatClientProtocolController.updateUserStatus(elt[0], elt[1])


    def userStatusUpdate(self, options):

        #si c'est l'utilisateur courant, on lui dit soi qu'il peut rejoindre la movie room voulue, soit qu'il peut quitter celle où il était, selon sa demande
        if options[0][1] == self.userId :
            if options[1][0] == 0:
                self.chatClientProtocolController.joinMovieOK()
            else:
                self.chatClientProtocolController.leaveRequestOK()
        #sinon on prévient l'utilisateur du changement de statut de l'utilisateur, dans l'ordre : déconnexion, arrivée dans la main room, arrivée dans une autre movie room
        else:
            if options[1][0] == 2:
                self.ackNum += 1
                self.sendPacket(0b1100, self.seqNum, self.userId, 0b11111111, 1, self.acknum)
                self.chatClientProtocolController.updateUserStatus(options[0][2], c2w_constants.ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM)
                self.seqNum += 1
            elif options[1][2] == 'MainRoom':
                self.ackNum += 1
                self.sendPacket(0b1100, self.seqNum, self.userId, 0b11111111, 1, self.acknum)
                self.chatClientProtocolController.updateUserStatus(options[0][2], c2w_constants.ROOM_IDS.MAIN_ROOM)
                self.seqNum += 1
            else:
                self.ackNum += 1
                self.sendPacket(0b1100, self.seqNum, self.userId, 0b11111111, 1, self.acknum)
                self.chatClientProtocolController.updateUserStatus(options[0][2], options[1][2])
                self.seqNum += 1


    def sendChatMessage(self, message):

        #on envoie au serveur le message que l'utilisateur a tapé
        self.sendPacket(0b1011, self.seqNum, self.userId, 0b11111111, 0, self.ackNum, [], message)
        self.seqNum += 1


    def receivedChatMessage(self, senderName, message):

        #on envoie à l'interface graphique le message reçu pour qu'il soit affiché
        self.ackNum += 1
        self.chatClientProtocolController.receivedChatMessage(senderName, message)
        #on acquitte au serveur la bonne réception du message
        self.sendPacket(0b1100, self.seqNum, self.userId, 0b11111111, 1, self.acknum)
        self.seqNum += 1


    def sendJoinMovie(self, movieTitle):

        #on envoie la demande de connexion à une movie room
        self.sendPacket(0b101, self.seqNum, self.userId, 0b11111111, 0, self.ackNum, [[0, self.userId, movieTitle]])
        self.seqNum += 1


    def sendleaveRequest(self):

        #on envoie la demande pour quitter la room actuelle (correspond à une déconnexion si l'utilisateur était dans la main room)
        self.sendPacket(0b1001, self.seqNum, self.userId, 0b11111111, 0, self.ackNum)
        self.seqNum += 1