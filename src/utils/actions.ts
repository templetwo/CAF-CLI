import { promises as fs } from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function handleRead(filePath: string): Promise<string> {
    try {
        const content = await fs.readFile(filePath, 'utf-8');
        return `File content of ${filePath}:\n${content}`;
    } catch (error: any) {
        return `Error reading file ${filePath}: ${error.message}`;
    }
}

export async function handleShell(command: string): Promise<string> {
    try {
        const { stdout, stderr } = await execAsync(command);
        if (stderr) {
            return `Error executing command: ${stderr}`;
        }
        return `Command output:\n${stdout}`;
    } catch (error: any) {
        return `Error executing command: ${error.message}`;
    }
}

export async function handleCode(filePath: string, content: string): Promise<void> {
    try {
        await fs.writeFile(filePath, content);
    } catch (error: any) {
        throw new Error(`Error writing to file ${filePath}: ${error.message}`);
    }
}

// This new function will handle git commands
export async function handleGit(args: string): Promise<string> {
  // We must first configure git inside the remote runner
  await handleShell(`git config --global user.name "CAF Agent"`);
  await handleShell(`git config --global user.email "agent@caf.cli"`);
  
  // Then execute the command
  return handleShell(`git ${args}`);
}
