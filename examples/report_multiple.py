"""Simple example to check integrations are correctly setup."""
import time

import meeshkan


def main():
    counter = 1
    exponent = 1
    while counter < 10:
        # Report two (and more) scalars using `meeshkan.report_scalar("name", value, "name2", value2, ...)`!
        meeshkan.report_scalar("counter", counter, "exponent", counter)
        time.sleep(2)
        counter += 1
        exponent += exponent


if __name__ == '__main__':
    main()
