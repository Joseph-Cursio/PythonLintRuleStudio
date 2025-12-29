"""
This script launches the Ruff Studio application, automatically selects a
directory provided as a command-line argument, and takes a screenshot
of the main window after a short delay to allow the UI to update.
"""
import subprocess
import time

def take_screenshot(output_path):
    """
    Takes a screenshot of the entire screen.

    Args:
        output_path (str): The path to save the screenshot to.
    """
    try:
        # Use xwd to capture the root window
        p1 = subprocess.Popen(["xwd", "-root", "-out", "root.xwd"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.communicate()

        # Use convert to save the captured image to the specified path
        p2 = subprocess.Popen(["convert", "root.xwd", output_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2.communicate()

        print(f"Screenshot saved to {output_path}")

    except FileNotFoundError:
        print("Error: 'xwd' or 'convert' command not found.")
        print("Please ensure that x11-apps and ImageMagick are installed.")

def main():
    """
    Launches the application and takes a screenshot.
    """
    app_process = None
    try:
        # Launch the application in the background using xvfb-run
        command = [
            "xvfb-run", "poetry", "run", "python", "-m",
            "src.ruff_studio.main", "."
        ]
        app_process = subprocess.Popen(
            command,
            cwd="ruff-studio"
        )

        # Wait for the application to load and process the directory
        time.sleep(10)

        # Take the screenshot
        take_screenshot("/home/jules/verification/verification.png")

    finally:
        if app_process:
            app_process.terminate()

if __name__ == "__main__":
    main()
