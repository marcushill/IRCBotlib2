import multiprocessing as mp
import asyncio
import os

def reader(pipe, loop):
    print(pipe.recv())
    loop.stop()

def subprocess(pipe):
    loop = asyncio.get_event_loop()
    loop.add_reader(pipe, reader, pipe, loop)
    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    pipe_name = 'bot_control'
    if not os.path.exists(pipe_name):
        os.mkfifo(pipe_name)
    control = open(pipe_name, 'r')
    while True:
        line =  control.read()
        print(line)
        if line is not b'':
            break
    control.close()
    # read, write = mp.Pipe()
    # print(read)
    # p = mp.Process(target=subprocess, args=(read,))
    # p.start()
    # write.send('kill')
    # p.join()
