import os
import sys
import argparse

if __name__ == "__main__":
    if "--window" in sys.argv:
        from run_window import play_in_window
        play_in_window()
    else:
        from ascii_video_player import main as video_main
        video_main()
