"""Simple example to check integrations are correctly setup."""
import time

import meeshkan


def main():
    counter = 1
    while counter < 10:
        meeshkan.report_scalar("counter", counter);
        time.sleep(2)
        counter += 1


if __name__ == '__main__':
    main()
