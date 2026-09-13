# EVN ALPHA Battery Status

A VS Code extension that displays the EVN ALPHA robotics controller's battery voltage and reading age in the status bar.

## Features

- **Non-interfering**: Reads from the existing `endurance_log.csv` file written by the autonomous tuning daemon — no serial port access, zero interference with running code
- **Real-time updates**: Watches the CSV file for changes and updates immediately when new data arrives
- **Reading age**: Shows how old the battery reading is (e.g., "7.815V (5s ago)")
- **Warning colors**: Status bar item turns warning color if reading is older than configured threshold (default 30 seconds)
- **Detailed tooltip**: Hover to see individual cell voltages, run ID, iteration, and exact timestamp

## Installation

1. Open the `evn-battery-status` folder in VS Code
2. Run `npm install` to install dependencies
3. Run `npm run compile` to build the extension
4. Press `F5` to launch a new Extension Development Host window
5. The extension will activate automatically

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `evnBatteryStatus.csvPath` | `bench/results/endurance_log.csv` | Path to CSV relative to workspace root |
| `evnBatteryStatus.updateIntervalMs` | `5000` | How often to poll the CSV (ms) |
| `evnBatteryStatus.showCells` | `true` | Show individual cell voltages in tooltip |
| `evnBatteryStatus.warnAgeSeconds` | `30` | Warning color if reading older than this |

## Status Bar Display

The status bar shows:
- `$(plug) 7.815V (5s ago)` — Green/normal when fresh
- `$(plug) 7.815V (45s ago)` — Yellow/warning when stale (configurable threshold)

Hover for details:
```
EVN ALPHA Battery
Pack: 7.815V
Cell 1: 3.889V
Cell 2: 3.883V
Reading age: 45s ago
Run: 0x2609062F, Iteration: 6
Last updated: 2:53:51 PM
```

## CSV Format Expected

The extension parses the `endurance_log.csv` format:
```
timestamp,iteration,runId,passed,total,cost,pack_mV,cell1_mV,cell2_mV,elapsed_s,profile
2026-09-13 14:53:51,6,0x2609062F,0,16,27.1937,7811,3886,3880,4.1770,nominal
```

## Requirements

- VS Code 1.80+
- Active workspace with the EVN ALPHA project open
- Autonomous daemon running (or CSV file present from previous runs)

## License

MIT