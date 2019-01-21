import time

import meeshkan


def my_loop():
    for i in range(10):
        meeshkan.report_scalar("i", i)
        time.sleep(2)


@meeshkan.as_blocking_job(job_name="test-job", report_interval_secs=10)
def main():
    my_loop()


# Besides decoration, you can also use meeshkan jobs as context managers:
def main_with_context_manager():
    job = meeshkan.create_external_job(name="my-job", poll_interval=10)
    with job:
        my_loop()


if __name__ == '__main__':

    meeshkan_agent_was_running = meeshkan.is_running()

    if not meeshkan_agent_was_running:
        # time.sleep(2)
        meeshkan.start()
        # time.sleep(2)
    main()

    if not meeshkan_agent_was_running:
        meeshkan.stop()
