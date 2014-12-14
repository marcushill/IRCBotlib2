import os
import os.path
import botlib
import multiprocessing as mp
import sys


def main():
    pipe_name = 'bot_control'
    # if not os.path.exists(pipe_name):
    # os.mkfifo(pipe_name)
    configs = [x for x in os.listdir('configs') if os.path.isfile('configs/' + x)]
    bots = {}
    for config in configs:
        r, w = mp.Pipe()
        bots[config] = {
            'read': r,
            'write': w,
            'process': mp.Process(target=botlib.start_bot,
                                  args=('configs/' + config, r, sys.stdout.fileno())) #  open('logs/' + config + '.log', 'w').fileno()))
        }
        bots[config]['process'].start()
    for key, bot in bots.items():
        bot['write'].send('kill')
        bot['process'].join()


if __name__ == '__main__':
    main()
