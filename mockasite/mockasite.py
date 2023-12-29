import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Mockasite: Record and serve back a mock version of a website")
    parser.add_argument('--capture', action='store_true', help='Record web interactions for later use.')
    parser.add_argument('--playback', action='store_true', help='Replay captured data as a functioning interactive mock of the original site.')
    parser.add_argument('--export', action='store_true', help='Export a standalone server that serves the mock website.')

    args = parser.parse_args()

    if args.capture:
        capture()
    elif args.playback:
        playback()
    elif args.export:
        export()
    else:
        parser.print_help()

    return 0

def capture():
    print("TODO: Implement capture functionality")

def playback():
    print("TODO: Implement playback functionality")

def export():
    print("TODO: Implement export functionality")

if __name__ == '__main__':
    sys.exit(main())
