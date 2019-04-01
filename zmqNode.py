'''
This is a class that imparts the ability to connect objects in as a zeroMQ
PAIR network.   It tracks multiple connections.

It uses json objects as messages and and these objects have 4 parts:
    subject - the node or the target of the node
    action - the method to be used
    args, kwarg - list of argument and dictionary of key word arguments
    ereply - expected reply message with 'e_reply' used a place holder for
        the results of subject.method(*args, **kwargs)

Recieving messages is non-blocking

'''
import zmq
import threading


class zmqNode():
    def __init__(self, name):
        self.name = name
        self.connections = {}
        self.context = zmq.Context()
        self.target = None
        self.heart_beat = 0.010  # how long to go between checks
        self.listening = False
        self.log = ''
        self.logfile = 'nodelog_' + name + '.txt'
        self.timer_listen = ''
        self.logging = False

    def setTarget(self, target):
        self.target = target

    def connect(self, name='', address='', server=False):
        # name is the name (string) of the thing it is connected to
        # address is the full address such as "tcp://127.0.0.1:5556"
        # server delineates if this is a server or client connection
        self.connections[name] = self.context.socket(zmq.PAIR)
        if server:
            self.connections[name].bind(address)
        else:
            self.connections[name].connect(address)
        self.connections[name].setsockopt(zmq.LINGER, 10)

    def disconnect(self, name=''):
        self.connections[name].close()

    def build_message(self, subject='', action='', args='', kwargs='', ereply=''):
        message = {}

        # Quick checks for valid values
        if type(subject) == str and subject != '':
            message['subject'] = subject
        elif subject != '':
            raise Exception(str(subject) + 'is not a valid message subject')

        if type(args) == list:
            message['args'] = args
        elif args != '':
            raise Exception('args was not of list type')

        if type(kwargs) == dict:
            message['kwargs'] = kwargs
        elif kwargs != '':
            raise Exception('kwargs was not of dictionary type.')

        if type(ereply) == dict:
            message['ereply'] = ereply
        elif ereply != '':
            raise Exception('ereply did not contain and "e_reply" target.')
        
        return message

    def findEReply(self, ereply):
        # So far this only search the first level of args and kwargs
        # Ideally I would like it to me able to search arbitrary structures
        if 'args' in ereply:
            if 'e_reply' in ereply['args']:
                return ereply['args'].index('e_reply')
        if 'kwargs' in ereply:
            for key in ereply['kwargs']:
                if ereply['kwargs'][key] == 'e_reply':
                    return key
        return False

    def send(self, name, message):
        self.connections[name].send_json(message)
        self.addlog('Sent ' + str(message))

    def start_listening(self):
        self.listening = True
        self.listen_all()

    def close(self):
        self.listening = False
        threading.Timer(2*self.heart_beat, self.close_all).start()

    def close_all(self):
        for connection in self.connections:
            self.disconnect(connection)
        self.context.term()

    def listen(self, name=''):
        message = 'no message'
        try:
            message = self.connections[name].recv_json(flags=zmq.NOBLOCK)
            self.cur_connection = name
        except zmq.Again:
            pass
        self.handle(message)

    def listen_all(self):
        for connection in self.connections:
            self.listen(name=connection)
        if self.listening:
            self.timer_listen = threading.Timer(self.heart_beat, self.listen_all).start()
        else:
            if type(self.timer_listen) == threading.Timer:
                self.timer_listen.cancel()

    def listen_once(self):
        for connection in self.connections:
            self.listen(name=connection)

    def zprint(self, message='blank'):
        print(message)

    def handle(self, message):
        if message == 'no message':
            return

        # Determine the intended target method
        # targetMethod defaults to self
        targetMethod = self
        if 'subject' in message:
                targetMethod = self.getMethod(message['subject'])

        # Pass the target method the correct data
        if targetMethod != '':
            if ('args' in message) and not ('kwargs' in message):
                tempresult = targetMethod(*message['args'])
            elif not ('args' in message) and ('kwargs' in message):
                tempresult = targetMethod(**message['kwargs'])
            elif ('args' in message) and ('kwargs' in message):
                tempresult = targetMethod(*message['args'], **message['kwargs'])
            else:
                if targetMethod != self:
                    tempresult = targetMethod()

        # Handle expected replies
        if 'ereply' in message:
            # Find the 'e_reply' tag in args or kwargs
            loc_ereply = self.findEReply(message['ereply'])
            # Replace that tag with subject.action(*args, **kwargs)
            if type(loc_ereply) == int:
                message['ereply']['args'][loc_ereply] = tempresult
            elif type(loc_ereply) == str:
                message['ereply']['kwargs'][loc_ereply] = tempresult
            reply_message = self.build_message(**message['ereply'])
            self.send(self.cur_connection, reply_message)

        self.addlog('Handled ' + str(message))

    def getMethod(self, maddress):
        madd_list = maddress.split('.')
        targetMethod = self
        for step in madd_list:
            if hasattr(targetMethod, step):
                targetMethod = getattr(targetMethod, step)
            else:
                raise Exception('Failed to find ' + str(step) + ' of ' + str(maddress))
        return targetMethod

    def addlog(self, message):
        if self.logging:
            try:
                logfile = open(self.logfile, mode='a')
            except:
                logfile = open(self.logfile, mode='w')
            logfile.write(str(message) + '\n')
            logfile.close()


if __name__ == '__main__':
    pass