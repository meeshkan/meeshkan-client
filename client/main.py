import sys
import threading
from .scheduler import Scheduler
from .job import Job, ProcessExecutable
from typing import List

# CLI COMMANDS AVAILABLE
LAUNCH = 'start'
STOP = 'stop'
LIST = 'list'
CANCEL = 'cancel'


class InputHandler(object):
    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler
        self.handlers = {
            LAUNCH: self.submit_job,
            STOP: self.stop,
            CANCEL: lambda job_id: scheduler.stop_job(int(job_id)),
            LIST: scheduler.list_jobs
        }

    def handle_input(self, user_input: str):
        cmd, args = self.parse_input(user_input)
        if cmd in self.handlers:
            func = self.handlers[cmd]
            if cmd is not None:
                func(*args)
        else:
            print('Unknown command', cmd)

    @staticmethod
    def parse_input(user_input: str):
        cmd_and_args = user_input.split(' ')
        cmd = cmd_and_args[0]
        args = cmd_and_args[1:]
        return cmd, args

    def submit_job(self, *args: str):
        """
        :param args: Sequence of program arguments fed into `Popen`
        :return: None
        """
        if len(args) == 0:
            print('Invalid command: give the script to execute!')
            return
        job_id = self.scheduler.get_id()
        executable = ProcessExecutable(args=args)
        job = Job(executable=executable, job_id=job_id)  # TODO Could use job creator
        self.scheduler.submit_job(job)

    def stop(self):
        self.scheduler.stop()
        sys.exit(0)


def main():
    with Scheduler() as scheduler:

        def notify(job, return_code):
            print("%s: Finished: %s with code %d" % (threading.current_thread().name, job, return_code))

        scheduler.register_listener(notify)

        input_handler = InputHandler(scheduler=scheduler)

        while True:
            user_input = input("Enter command (\"%s\" to exit):\n" % STOP)
            input_handler.handle_input(user_input=user_input)


if __name__ == '__main__':
    main()
