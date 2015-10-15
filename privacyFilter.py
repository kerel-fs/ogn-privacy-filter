#!/usr/bin/env python3
# ogn-privacy-filter - A script to selectively forward APRS packets.
# Copyright (C) 2015  Fabian P. Schmidt
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import select
import socket
import sys
import queue
import time
from aprslib import parse, ParseError
from ognutils import getDDB, listTrackable


class privacyFilter:
    # Check packets from client
    def checkPacket(self,packet):
        if packet.decode('latin-1')[0] == '#':
            # Client Banner
            return True
        else:
            try:
                parsed = parse(packet)
                if parsed['from'] in self.trackable:
                    return True
                else:
                    print("Drop packet from %s (noTrack): %s"%(str(parsed['from']),str(packet)))
                    return False
            except ParseError:
                if packet.startswith(b'user'):
                    callsign = packet.split(b' ')[1].decode('latin-1')
                    print("Detected own callsign: %s"%callsign)
                    self.callsigns.append(callsign)
                    self.trackable.append(callsign)
                    # Login phrase detected
                    return True
                else:
                    print("Drop invalid packet: %s"%str(packet))
                    return False


    # NOTE: Locks EventLoop during execution
    def updateDDB(self):
        self.trackable = listTrackable(getDDB())
        self.trackable.extend(self.callsigns)
        print('Updated trackable list (from DDB), %i entries.'%len(self.trackable))


    def connectToServer(self):
        connected = False
        while not connected:
            try:
                self.server = socket.create_connection(self.server_address, 15)
                connected = True
            except (socket.timeout, ConnectionRefusedError):
                print("Connect failed for %s:%s, retry..."%self.server_address)
                time.sleep(10)
        self.server.setblocking(0)
        print("Connected to server %s:%s"%self.server.getpeername())


    def closeConnection(self,s):
        # No data received, closed connection
        self.inputs.remove(s)
        if s in self.outputs:
            self.outputs.remove(s)
        s.close()

        if s == self.server:
            # Server disconnected
            print("Server disconnected, can't forward packets.")
            del self.server
            self.connectToServer()
            self.inputs.append(self.server)
        else:
            # Client disconnected
            print("Client disconnected, wait for reconnect...")
            self.client_connected = False


    def __init__(self,clients_address = ('127.0.2.1', 14580), server_address = ('aprs-pool.glidernet.org', 14580), ddbInterval = 60):
        self.clients = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients.setblocking(0)
        
        print('Listen for new client at %s:%s' % clients_address)
        self.clients.bind(clients_address)
        self.clients.listen(1)

        self.interval = ddbInterval
        self.server_address = server_address

        self.callsigns = []

        # APRS Server Properties
        self.newline = b'\r\n'
        

    def run(self):
        self.connectToServer()

        self.inputs = [self.clients, self.server]
        self.outputs = []
        self.client_connected = False
        
        # Flow diagram:
        # station --> buf --> checkPacket() --> client_queue --> aprs-server
        # aprs-server --> server_queue --> station

        # Outgoing message queues
        client_queue = queue.Queue()
        server_queue = queue.Queue()

        # Incoming buffer
        buf = b''

        # Timer
        self.updateDDB()
        lasttime = time.time()


        while self.inputs:
            timeout = self.interval + lasttime - time.time()
            if timeout <= 0:
                self.updateDDB()
                lasttime = time.time()
                timeout = self.interval

            readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs, timeout)

            if not (readable or writable or exceptional):
                self.updateDDB()
                lasttime = time.time()
                continue
        
            for s in readable:
                if s is self.clients:
                    # Accept new client connection
                    if not self.client_connected:
                        connection, client_address = s.accept()
                        connection.setblocking(0)
                        self.inputs.append(connection)
                        self.client = connection
                        self.client_connected = True
                        print("New client at %s:%s"%client_address)
                    else:
                         print("A client is already connected")
                else:
                    data = s.recv(1024)
                    print("Received at port %s: %s"%(s.getpeername()[1],data))
                    if data:
                        # Received data
                        if s == self.server:
                            # from Server
                            server_queue.put(data)
                            if self.client_connected and not self.client in self.outputs:
                                self.outputs.append(self.client)
                        else:
                            # from Client
                            buf += data
                            if self.newline in buf:
                                lines = buf.split(self.newline)
                                buf = lines[-1]
                                for line in lines[:-1]:
                                    if self.checkPacket(line):
                                        client_queue.put(line+self.newline)
                            if not self.server in self.outputs:
                                self.outputs.append(self.server)
                    else:
                        # Received no data, close connection
                        self.closeConnection(s)
        
            # Handle Outputs
            for s in writable:
                if s == self.server:
                    # to Server
                    try:
                        next_msg = client_queue.get_nowait()
                    except queue.Empty:
                        self.outputs.remove(s)
                    else:
                        print("Send %s"%next_msg)
                        s.send(next_msg)
                else:
                    # to Client
                    try:
                        next_msg = server_queue.get_nowait()
                    except queue.Empty:
                        self.outputs.remove(s)
                    else:
                        print("Send %s"%next_msg)
                        s.send(next_msg)
        
            # Handle exceptional conditions
            for s in exceptional:
                print("Exceptional condition:")
                self.closeConnection(s)


if __name__ == "__main__":
    f = privacyFilter()
    f.run()
