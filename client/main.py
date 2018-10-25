if __package__ is None:
    raise Exception('Run with -m instead.')


def main():
    from . import core
    core.hmm()


if __name__ == '__main__':
    main()
