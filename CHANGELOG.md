# Changelog

All notable changes to this project will be documented in this file.

## [0.4.2] - 2026-02-16

### Changed
- Renamed "Sound Duration" to "Activation Duration" across UI, code, and documentation for better clarity.

## [0.4.1] - 2026-02-16

### Added
- Left-clicking the tray icon now toggles between Pause and Resume.

## [0.4.0] - 2026-02-16

### Added
- Dynamic tray icon states (active, armed, unarmed) to indicate monitoring status.

### Changed
- Simplified "Idle" status text by removing the "(Waiting for sound)" suffix.

## [0.3.1] - 2026-02-16

### Added
- Display arming status in the main menu when "Wait for Sound" is enabled.

## [0.3.0] - 2026-02-16

### Added
- Smart auto-resume: waits for non-Spotify sound before arming auto-resume.
- New tray menu options for "Wait for Sound" and "Sound Duration".
- Codebase formatted with black and isort.

## [0.2.0] - 2026-02-16

### Added
- Independent toggles for Spotify and System volume control in the tray menu.

## [0.1.0] - 2026-02-13

### Added
- Initial release.
- Audio monitoring to detect silence.
- Automatic Spotify playback resume.
- System tray icon with configuration options for timeout, threshold, and volume.
