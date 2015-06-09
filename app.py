#!python3

import os
import os.path
import botlib
import multiprocessing as mp
import sys


def main():
    pipe_name = 'bot_control'

    if not os.path.exists(pipe_name):
        os.mkfifo(pipe_name)

    control = os.open(pipe_name, os.O_RDONLY|os.O_NONBLOCK)
    configs = [x for x in os.listdir('configs') if os.path.isfile('configs/' + x)]
    bots = {}
    for config in configs:
        r, w = mp.Pipe()
        
        bots[config] = {
            'read': r,
            'write': w,
            'process': mp.Process(target=botlib.start_bot,
                                  args=('configs/' + config, r, 'logs/' + config + '.log'))
        }
        bots[config]['process'].start()
        print('Started')

    while True:
        line = os.read(control, 2048).decode('utf-8').strip('\n\r')
        if line == 'kill':
            os.close(control)
            for key, bot in bots.items():
                bot['write'].send('kill')
                bot['process'].join()
            break   

if __name__ == '__main__':
    main()
