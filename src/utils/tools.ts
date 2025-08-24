import { Tool } from '@langchain/core/tools';
import { exec } from 'child_process';
import { promisify } from 'util'; // Added import

const execPromise = promisify(exec);

class GitTool extends Tool {
  name = 'git_tool';
  description = 'Execute Git commands safely. Input: JSON with {command: string, args: array}. Examples: {command: "checkout", args: ["-b", "new-branch"]}';

  async _call(input: string) {
    try {
      const { command, args } = JSON.parse(input);
      const fullCmd = `git ${command} ${args.join(' ')}`;
      const { stdout, stderr } = await execPromise(fullCmd);
      return stdout || stderr;
    } catch (error: any) {
      return `Error: ${error.message}`;
    }
  }
}

class SedTool extends Tool {
  name = 'sed_tool';
  description = 'Execute sed commands. Input: JSON with {expression: string, file: string, options: string (e.g., "-i.bak")}. Example: {expression: "s/old/new/g", file: "file.txt", options: "-i"}';

  async _call(input: string) {
    try {
      const { expression, file, options } = JSON.parse(input);
      const fullCmd = `sed ${options || ''} '${expression}' ${file}`;
      const { stdout, stderr } = await execPromise(fullCmd);
      return stdout || stderr;
    } catch (error: any) {
      return `Error: ${error.message}`;
    }
  }
}

export const tools = [new GitTool(), new SedTool()]; // Export instances of the classes

export async function handleToolCall(toolCall: { name: string; args: any }): Promise<string> {
  const tool = tools.find(t => t.name === toolCall.name);
  if (tool) {
    return await tool._call(JSON.stringify(toolCall.args)); // Call the _call method with stringified args
  } else {
    return `Error: Tool ${toolCall.name} not found.`;
  }
}
