"""Thin entrypoint delegating daily state updates to rebuild_state.rebuild()."""
import json
from rebuild_state import rebuild


def main():
    print(json.dumps(rebuild()))


if __name__ == '__main__':
    main()
