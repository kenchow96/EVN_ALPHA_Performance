import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

interface BatteryReading {
    timestamp: Date;
    packVoltage: number;
    cell1Voltage: number;
    cell2Voltage: number;
    runId: string;
    iteration: number;
}

export function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('evnBatteryStatus');
    
    // Create status bar item (right side, low priority so it appears on the right)
    const statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.name = 'EVN ALPHA Battery';
    statusBarItem.tooltip = 'EVN ALPHA Battery Voltage';
    statusBarItem.show();
    
    let updateTimer: NodeJS.Timeout | undefined;
    
    function updateStatusBar() {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            statusBarItem.text = '$(plug) EVN: No workspace';
            return;
        }
        
        const workspaceRoot = workspaceFolders[0].uri.fsPath;
        const csvPath = config.get<string>('csvPath', 'bench/results/endurance_log.csv');
        const fullCsvPath = path.join(workspaceRoot, csvPath);
        const showCells = config.get<boolean>('showCells', true);
        const warnAgeSeconds = config.get<number>('warnAgeSeconds', 30);
        
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
            let ageStr: string;
            if (ageSeconds < 60) {
                ageStr = `${ageSeconds}s ago`;
            } else if (ageSeconds < 3600) {
                ageStr = `${Math.floor(ageSeconds / 60)}m ${ageSeconds % 60}s ago`;
            } else {
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
            } else {
                statusBarItem.color = undefined;
                statusBarItem.backgroundColor = undefined;
            }
            
        } catch (err) {
            statusBarItem.text = '$(plug) EVN: Error';
            statusBarItem.tooltip = `Error reading battery: ${err}`;
            statusBarItem.color = new vscode.ThemeColor('statusBarItem.errorForeground');
        }
    }
    
    // Initial update
    updateStatusBar();
    
    // Set up periodic updates
    const updateIntervalMs = config.get<number>('updateIntervalMs', 5000);
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
        const csvPath = config.get<string>('csvPath', 'bench/results/endurance_log.csv');
        const fullCsvPath = path.join(workspaceFolders[0].uri.fsPath, csvPath);
        
        const watcher = vscode.workspace.createFileSystemWatcher(fullCsvPath);
        watcher.onDidChange(() => updateStatusBar());
        context.subscriptions.push(watcher);
    }
    
    // Clean up on deactivate
    context.subscriptions.push(
        statusBarItem,
        configChangeListener,
        { dispose: () => { if (updateTimer) clearInterval(updateTimer); } }
    );
}

export function deactivate() {}