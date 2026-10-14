"""Disposable loopback SSH endpoint. Real Paramiko transport, Cisco-style shell."""
import socket
import threading
import paramiko

class Server(paramiko.ServerInterface):
    def __init__(self, owner): self.owner=owner
    def check_auth_password(self, username, password):
        self.owner.connections.append(username)
        return paramiko.AUTH_SUCCESSFUL if not self.owner.reject and username=='backup' and password=='test-password' else paramiko.AUTH_FAILED
    def get_allowed_auths(self, username):return 'password'
    def check_channel_request(self, kind, chanid):return paramiko.OPEN_SUCCEEDED if kind=='session' else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
    def check_channel_pty_request(self,*args):return True
    def check_channel_shell_request(self,channel):return True

class SSHDevice:
    def __init__(self, incomplete=False, reject=False):self.incomplete=incomplete;self.reject=reject
    def __enter__(self):
        self.connections=[];self.commands=[];self.stop=threading.Event();self.transports=[]
        self.key=paramiko.RSAKey.generate(2048)
        self.socket=socket.socket();self.socket.bind(('127.0.0.1',0));self.port=self.socket.getsockname()[1];self.socket.listen();self.socket.settimeout(.1)
        def serve(client):
            transport=paramiko.Transport(client);self.transports.append(transport);transport.add_server_key(self.key)
            try:
                transport.start_server(server=Server(self));channel=transport.accept(3)
                if channel is None:return
                channel.send('\r\nR1#');pending=b''
                while not self.stop.is_set():
                    chunk=channel.recv(4096)
                    if not chunk:break
                    pending+=chunk
                    while b'\n' in pending:
                        line,pending=pending.split(b'\n',1);cmd=line.decode().strip();self.commands.append(cmd)
                        output='version 15.2\r\nhostname R1\r\ninterface Loopback0\r\n description controlled SSH integration\r\nend' if cmd.startswith('show ') else ''
                        channel.send(cmd+'\r\n'+output+('\r\n' if self.incomplete and cmd.startswith('show ') else '\r\nR1#'))
            except (EOFError,OSError,paramiko.SSHException):pass
            finally:transport.close()
        def accept():
            while not self.stop.is_set():
                try:client,_=self.socket.accept()
                except socket.timeout:continue
                except OSError:break
                threading.Thread(target=serve,args=(client,),daemon=True).start()
        self.thread=threading.Thread(target=accept,daemon=True);self.thread.start();return self
    def __exit__(self,*args):
        self.stop.set();self.socket.close()
        for transport in self.transports:transport.close()
        self.thread.join(2)
