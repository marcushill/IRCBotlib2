import asyncio
import socket
import pystache
import random
import json
import re
import sys


class Event:
    def __init__(self, period, steps):
        self.period = period
        self.steps = steps
        self.remaining = period
        self.vars = {}


class SleepStep:
    def __init__(self, period):
        self.period = period

    @asyncio.coroutine
    def execute(self):
        yield from asyncio.sleep(self.period)


class MessageStep:
    def __init__(self, messages, bot, dict):
        self.messages = messages
        self.bot = bot
        self.dict = dict

    @asyncio.coroutine
    def execute(self):
        message = random.choice(self.messages)
        message = pystache.render(message, self.dict)
        self.bot.sendmsg(self.bot.channel, pystache.render(message, self.dict))


class ActionStep:
    def __init__(self, action, bot, dict):
        self.action = action
        self.bot = bot
        self.dict = dict

    @asyncio.coroutine
    def execute(self):
        message = pystache.render(self.action, self.dict)
        self.bot.action(self.bot.channel, pystache.render(message, self.dict))


class StoreStep:
    def __init__(self, varname, string, dict):
        self.name = varname
        self.template = string
        self.dict = dict

    @asyncio.coroutine
    def execute(self):
        self.dict[self.name] = pystache.render(self.template, self.dict)


class Trigger:
    def __init__(self, pattern, responses, isAction, isCommand, *args):
        self.regex = re.compile(pattern, re.I)
        self.action = isAction
        self.responses = responses
        self.groups = args
        self.command = isCommand

    def attempt(self, message):
        match = self.regex.match(message)
        if match and len(self.groups) > 0:
            for group in self.groups:
                if not group.match(match.group(group.name)):
                    return False
            return True
        elif match:
            return True
        return False

    def get_response(self):
        return random.choice(self.responses)


class Group:
    def __init__(self, group, *args):
        self.name = group
        self.allow = [re.compile(x, re.I) for x in args]

    def match(self, string):
        for item in self.allow:
            if item.match(string):
                return True
        return False


class IRCBotProtocol(asyncio.Protocol):
    def __init__(self, nick, channel, ident, loop, triggers, queue, stopper):
        self.loop = loop
        self.triggers = triggers
        self.channel = channel
        self.nick = nick
        self.ident = ident
        self.queue = queue
        self.stopper = stopper

    def sendmsg(self, chan, msg):
        self.send("PRIVMSG " + chan + " :" + msg + "\r\n")

    def joinchan(self, chan):
        self.send("JOIN " + chan + "\r\n")

    def send(self, msg):
        self.sock.write(msg.encode('utf-8'))

    def action(self, chan, action):
        self.sendmsg(chan, '\x01ACTION ' + action + '\x01')

    @asyncio.coroutine
    def handle_message(self, ircmsg):
        yield from self.queue.put("\n\n" + ircmsg + "\n\n")
        for item in self.triggers:
            if item.attempt(ircmsg):
                if item.command:
                    if item.get_response() == 'quit':
                        self.end()
                        return
                if item.action:
                    self.action(self.channel, item.get_response())
                    break
                else:
                    self.sendmsg(self.channel, item.get_response())
                    break

    def connection_made(self, transport):
        print('Connection made!')
        self.sock = transport
        self.send("USER " + self.nick + " " + self.nick + " " + self.nick + " : " + self.ident + "\r\n")
        self.send("NICK " + self.nick + "\r\n")
        self.loop.call_later(3,self.joinchan, self.channel)
        self.stopper.clear()
        print('Nick set up done')

    def end(self):
        self.sock.close()

    def data_received(self, data):
        ircmsg = data.decode('utf-8').strip('\n\r')
        print(ircmsg)
        if ircmsg.find("PING :") != -1:
            pingid = ircmsg.split(':')
            self.send("PONG " + pingid[-1] + "\r\n")
        else:
            asyncio.async(self.handle_message(ircmsg))

    def connection_lost(self, exc):
        print('Connection closed')
        self.stopper.set()
        self.loop.stop()


def create_bot(config, loop):
    triggers = []
    for trigger in config['triggers']:
        groups = []
        regex = trigger['pattern']
        if 'isCommand' not in trigger:
            trigger['isCommand'] = False
        for key, value in trigger.items():
            if key in ('responses', 'pattern', 'isAction', 'isCommand'):
                continue
            groups.append(Group(key, *value))
        triggers.append(Trigger(regex, trigger['responses'], trigger['isAction'], trigger['isCommand'], *groups))
    queue = asyncio.Queue()
    stopper = asyncio.Event()
    stopper.set()
    return IRCBotProtocol(config['nick'], config['channel'], config['ident'], loop, triggers, queue, stopper), event_manager(queue, [], stopper)

@asyncio.coroutine
def event_manager(queue, events, stopper):
    message = yield from queue.get()
    asyncio.async(event_manager(queue, events, stopper))


@asyncio.coroutine
def process_signal(pipe, bot):
    sig = pipe.recv().decode('utf-8').strip('\n\r')
    print("Recieved Signal: ", sig)
    if sig == 'kill':
        bot.close()


def start_bot(config, r, w):
    # Create a pair of connected sockets
    #sys.stdout = open(w, 'w')
    with open(config) as f:
        loop = asyncio.get_event_loop()
        config = json.load(f)
        bot, event_manager = create_bot(config, loop)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((config['server'], 6667))
    coro = loop.create_connection(lambda: bot, sock=sock)
    asyncio.async(coro)
    loop.add_reader(r.fileno(), process_signal, r, bot)
    asyncio.async(event_manager)
    loop.run_forever()
    loop.close()

