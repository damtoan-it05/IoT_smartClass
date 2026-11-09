"""Person detection, sharing camera and inference options with count_people."""
import sys
from count_people import main

if __name__ == '__main__':
    sys.argv.append('--detect-only')
    main()
