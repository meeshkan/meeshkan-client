"""Simple example to check integrations are correctly setup."""
import time

import meeshkan


def check_exp(e):
    return e > 100

# Condition for 2 parameters; report when counter (c) is an odd number greater than 3
# Conditions can be added before the actual values are added/reported to Meeshkan!
# If a scalar value doesn't exist, Meeshkan naturally replaces it with the value 1, so your code won't crash.
meeshkan.add_condition("counter", "constant", condition=lambda c, const: c > 3 and c % const == 1)
def main():
    counter = 1
    exponent = 1
    constant = 2
    # Condition can also be a non-lambda function; here we add another condition for reporting when exponent > 100
    # When using a condition, all parameters in a given Job are reported, unless asked otherwise
    meeshkan.add_condition("exponent", condition=check_exp, only_reported=True)
    while counter < 10:
        meeshkan.report_scalar("counter", counter, "exponent", exponent, "constant", constant)
        time.sleep(2)
        counter += 1
        exponent += exponent


if __name__ == '__main__':
    main()
