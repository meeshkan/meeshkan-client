import time

import meeshkan


def main():
    job = meeshkan.create_external_job(name="my-job", poll_interval=10)
    with job:
        for i in range(10):
            meeshkan.report_scalar("i", i)
            time.sleep(2)


if __name__ == '__main__':
    main()
