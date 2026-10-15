"""Deprecated compatibility entry point: report pins without rewriting evidence."""
from diagnose_pins import main


if __name__ == '__main__':
    print('repin_all is now read-only. Studio resolves known old bundled pins for new runs. '
          'Historical job locks and saved documents are never rewritten by this command.')
    main()
