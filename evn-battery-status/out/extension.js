"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
function activate(context) {
    const config = vscode.workspace.getConfiguration('evnBatteryStatus');
    // Create status bar item (right side, low priority so it appears on the right)
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.name = 'EVN ALPHA Battery';
    statusBarItem.tooltip = 'EVN ALPHA Battery Voltage';
    statusBarItem.show();
    let updateTimer;
    function updateStatusBar() {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            statusBarItem.text = '$(plug) EVN: No workspace';
            return;
        }
        const workspaceRoot = workspaceFolders[0].uri.fsPath;
        const csvPath = config.get('csvPath', 'bench/results/endurance_log.csv');
        const fullCsvPath = path.join(workspaceRoot, csvPath);
        const showCells = config.get('showCells', true);
        const warnAgeSeconds = config.get('warnAgeSeconds', 30);
        try {
            if (!fs.existsSync(fullCsvPath)) {
                statusBarItem.text = '$(plug) EVN: No CSV';
                statusBarItem.color = undefined;
                return;
            }
            const content = fs.readFileSync(fullCsvPath, 'utf8');
            const lines = content.trim().split('\n');
            if (lines.length === 0) {
                statusBarItem.text = '$(plug) EVN: Empty CSV';
                return;
            }
            // Get the last line (most recent reading)
            const lastLine = lines[lines.length - 1].trim();
            if (!lastLine) {
                statusBarItem.text = '$(plug) EVN: No data';
                return;
            }
            // Parse CSV: timestamp,iteration,runId,passed,total,cost,pack_mV,cell1_mV,cell2_mV,elapsed_s,profile
            const fields = lastLine.split(',');
            if (fields.length < 10) {
                statusBarItem.text = '$(plug) EVN: Parse error';
                return;
            }
            const timestampStr = fields[0];
            const iteration = parseInt(fields[1]);
            const runId = fields[2];
            const pack_mV = parseInt(fields[6]);
            const cell1_mV = parseInt(fields[7]);
            const cell2_mV = parseInt(fields[8]);
            const packVoltage = pack_mV / 1000;
            const cell1Voltage = cell1_mV / 1000;
            const cell2Voltage = cell2_mV / 1000;
            // Parse timestamp and calculate age
            const readingTime = new Date(timestampStr);
            const now = new Date();
            const ageMs = now.getTime() - readingTime.getTime();
            const ageSeconds = Math.floor(ageMs / 1000);
            // Format age string
            let ageStr;
            if (ageSeconds < 60) {
                ageStr = `${ageSeconds}s ago`;
            }
            else if (ageSeconds < 3600) {
                ageStr = `${Math.floor(ageSeconds / 60)}m ${ageSeconds % 60}s ago`;
            }
            else {
                ageStr = `${Math.floor(ageSeconds / 3600)}h ${Math.floor((ageSeconds % 3600) / 60)}m ago`;
            }
            // Build status bar text
            const voltageStr = `${packVoltage.toFixed(3)}V`;
            statusBarItem.text = `$(plug) ${voltageStr} (${ageStr})`;
            // Build tooltip
            let tooltip = `EVN ALPHA Battery\n`;
            tooltip += `Pack: ${packVoltage.toFixed(3)}V\n`;
            if (showCells) {
                tooltip += `Cell 1: ${cell1Voltage.toFixed(3)}V\n`;
                tooltip += `Cell 2: ${cell2Voltage.toFixed(3)}V\n`;
            }
            tooltip += `Reading age: ${ageStr}\n`;
            tooltip += `Run: ${runId}, Iteration: ${iteration}\n`;
            tooltip += `Last updated: ${readingTime.toLocaleTimeString()}`;
            statusBarItem.tooltip = tooltip;
            // Set color based on age
            if (ageSeconds > warnAgeSeconds) {
                statusBarItem.color = new vscode.ThemeColor('statusBarItem.warningForeground');
                statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
            }
            else {
                statusBarItem.color = undefined;
                statusBarItem.backgroundColor = undefined;
            }
        }
        catch (err) {
            statusBarItem.text = '$(plug) EVN: Error';
            statusBarItem.tooltip = `Error reading battery: ${err}`;
            statusBarItem.color = new vscode.ThemeColor('statusBarItem.errorForeground');
        }
    }
    // Initial update
    updateStatusBar();
    // Set up periodic updates
    const updateIntervalMs = config.get('updateIntervalMs', 5000);
    updateTimer = setInterval(updateStatusBar, updateIntervalMs);
    // Watch for config changes
    const configChangeListener = vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('evnBatteryStatus')) {
            updateStatusBar();
        }
    });
    // Watch for file changes to update immediately when new data arrives
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (workspaceFolders && workspaceFolders.length > 0) {
        const csvPath = config.get('csvPath', 'bench/results/endurance_log.csv');
        const fullCsvPath = path.join(workspaceFolders[0].uri.fsPath, csvPath);
        const watcher = vscode.workspace.createFileSystemWatcher(fullCsvPath);
        watcher.onDidChange(() => updateStatusBar());
        context.subscriptions.push(watcher);
    }
    // Clean up on deactivate
    context.subscriptions.push(statusBarItem, configChangeListener, { dispose: () => { if (updateTimer)
            clearInterval(updateTimer); } });
}
function deactivate() { }
//# sourceMappingURL=extension.js.map