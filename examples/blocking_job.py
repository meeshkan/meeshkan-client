import math
import time

import meeshkan


def my_loop():
    iterations = 20
    for i in range(20):
        meeshkan.report_scalar("y", math.sin(i * 2 * math.pi / iterations))
        time.sleep(1)


@meeshkan.as_blocking_job(job_name="test-job", report_interval_secs=10)
def main():
    my_loop()


# Besides decoration, you can also use meeshkan jobs as context managers:
def main_with_context_manager():
    job = meeshkan.create_blocking_job(name="my-job", report_interval_secs=10)
    with job:
        my_loop()


if __name__ == '__main__':

    meeshkan_agent_was_running = meeshkan.is_running()

    if not meeshkan_agent_was_running:
        meeshkan.start()

    main()

    if not meeshkan_agent_was_running:
        meeshkan.stop()
