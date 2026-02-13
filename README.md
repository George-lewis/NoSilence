# NoSilence

If your attention is as bad as mine and like me always need to have something playing but can't always be bothered to unpause Spotify when you're jumping between calls and videos then this is for you. This is a program that periodically checks your system audio and after a period of silence it will unpause Spotify for you. It's a Python program built for Windows with a tray icon, and most every parameter is configurable. You can use build.ps1 to build an .exe with pyinstaller, then run it on boot. This program was 95% vibe coded. Contributions are welcome.

## Features

*   **Silence Detection:** Monitors your system's audio output and detects when there is no sound playing.
*   **Automatic Resume:** Resumes Spotify playback on your chosen device after a configurable period of silence.
*   **System Tray Integration:** Runs discreetly in the system tray.
*   **Device Selection:** Choose which Spotify device to control from the tray menu.
*   **Pause/Resume:** Temporarily disable/enable the automatic resume feature.
*   **Configurable Timeout:** Select how long the system should be silent before resuming playback.
*   **Configurable Polling Interval:** Choose how often the system checks for audio status.
*   **Configurable Silence Threshold:** The minimum volume level below which audio is considered "silent." This prevents the application from mistakenly resuming playback during very quiet passages of music or system sounds that are not true silence. The application monitors the peak audio output of your system, which is a value between 0.0 (complete silence) and 1.0 (maximum volume). The default threshold is `0.001` (0.1%).
*   **Configurable Resume Volume:** Separately configure the resume volume for both Spotify and the system master volume.
*   **Fallback Playback:** If it can't resume the previous track, it will try to start Spotify's "DJ" or a default playlist.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/George-lewis/nosilence.git
    cd nosilence
    ```

2.  **Create a Python virtual environment:**
    ```bash
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

3.  **Install dependencies:**
    ```bash
    pip install .
    ```

4.  **Create your `secrets.json` file:**

    In the root directory, create a file named `secrets.json`. This is where you'll put your Spotify API credentials.

    ```json
    {
      "CLIENT_ID": "your_spotify_client_id",
      "CLIENT_SECRET": "your_spotify_client_secret"
    }
    ```

    You can get your `CLIENT_ID` and `CLIENT_SECRET` by creating an app on the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications).

    When you create your app, you must also set a **Redirect URI**. Please set it to `https://127.0.0.1:8888` in your Spotify app settings.

## Usage

To run the application directly from the source code, execute the `main.py` script:

```bash
python src/main.py
```

The application will start in your system tray. The first time you run it, you will be prompted to log in to your Spotify account in your web browser.

### System Tray Menu

*   **Status**: The first menu item displays the current status of the program (e.g., "Monitoring...", "Resuming in 5s", "Paused").
*   **Pause/Resume**: Temporarily pause or resume the automatic monitoring.
*   **Devices**: A list of your available Spotify devices. Select one to set it as the target for playback.
*   **Silence Timeout**: Choose how many seconds of silence should pass before playback resumes. Includes an "Other..." option for custom input.
*   **Polling Interval**: Choose how often the system checks for audio status. Includes an "Other..." option for custom input.
*   **Silence Threshold**: Choose the volume threshold for silence detection. Includes an "Other..." option for custom input.
*   **Spotify Volume**: Set the volume for Spotify when playback resumes. Includes an "Other..." option for custom input.
*   **System Volume**: Set the system master volume when playback resumes. Includes an "Other..." option for custom input.
*   **Quit**: Exits the application.

## Building the Executable

You can build a standalone `.exe` file for the application using `PyInstaller`.

1.  Make sure you have the development dependencies installed:
    ```bash
    pip install ".[dev]"
    ```
2.  Run the `build.ps1` script from a PowerShell terminal:

    ```powershell
    .\build.ps1
    ```

The executable will be created in the `dist` folder. You will need to copy the `secrets.json` file into the `dist` folder next to the executable for it to work.

## Configuration

The application creates a `config.json` file in the root of the project (or next to the executable) to store your preferences.

*   `spotify_device`: The name of the Spotify device to control.
*   `silence_timeout`: The duration in seconds to wait before resuming playback.
*   `silence_threshold`: The volume threshold for silence detection.
*   `polling_interval`: The interval in seconds between audio checks.
*   `spotify_volume_percent`: The volume percentage for Spotify when playback resumes.
*   `system_volume_percent`: The system master volume percentage when playback resumes.

You can edit this file manually, but it's recommended to use the system tray menu to configure the application.

## Dependencies

*   [spotipy](https://spotipy.readthedocs.io/)
*   [pystray](https://pystray.readthedocs.io/)
*   [Pillow](https://python-pillow.org/)
*   [pycaw](https://github.com/AndreMiras/pycaw)
*   [comtypes](https://pythonhosted.org/comtypes/)
*   [requests](https://requests.readthedocs.io/)
*   [rich](https://github.com/Textualize/rich)
*   [pywin32](https://github.com/mhammond/pywin32)
