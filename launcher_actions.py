import os
import webbrowser


def launch_item(item):
    target = item["target"]
    if item.get("type") == "url":
        webbrowser.open(target)
    else:
        # apps (.lnk/.exe) and folders both open correctly via startfile,
        # exactly like double-clicking them in Explorer.
        os.startfile(target)
