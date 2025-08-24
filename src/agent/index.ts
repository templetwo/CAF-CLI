import { Command } from 'commander';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { handleRead, handleShell, handleCode, handleGit } from '../utils/actions.js';
import 'dotenv/config';

const program = new Command();

// Initialize the Google AI Client
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });

interface Context {
  goal: string;
  history: { action: string; observation: string }[];
}

/**
 * Asks the LLM for the next step based on the current context.
 */
async function askForNextStep(context: Context): Promise<string> {
  console.log("> Thinking...");

  const prompt = `
    You are an autonomous CLI agent. Your goal is to achieve the following objective: "${context.goal}".

    Here is the history of actions you have taken so far:
    ${context.history.map(h => `- Action: ${h.action}\n  Observation: ${h.observation}`).join('\n') || 'No actions taken yet.'}

    Based on the goal and the history, what is the single next action you should take?
    Your response MUST be in the format: ACTION:ARGUMENT
    Valid actions are: READ, SHELL, CODE, GIT, FINISH.

    Example Responses:
    - READ:./src/utils/actions.ts
    - SHELL:ls -la
    - CODE:./newFile.ts:console.log("Hello World");
    - GIT:commit -am "feat: agent self-modification"
    - GIT:push
    - FINISH:The goal has been achieved.

    Provide only the next action.
  `;

  try {
    const result = await model.generateContent(prompt);
    const response = await result.response;
    const nextAction = response.text().trim();
    return nextAction;
  } catch (error) {
    console.error("Error contacting the oracle:", error);
    return "FINISH:Error occurred, stopping agent.";
  }
}

/**
 * The main agentic loop.
 */
async function agentLoop(goal: string) {
  const context: Context = {
    goal,
    history: [],
  };

  console.log(`Goal: ${goal}\n--------------------`);

  for (let i = 0; i < 10; i++) { // Safety break after 10 steps
    const nextAction = await askForNextStep(context);

    if (!nextAction || !nextAction.includes(':')) {
        console.log(`> Observation: Invalid action format from LLM: "${nextAction}". Finishing.`);
        break;
    }

    const [action, argument] = nextAction.split(':', 2);
    console.log(`> Action: ${action}:${argument}`);

    if (action === 'FINISH') {
      console.log('> Observation: Goal achieved or finishing loop.');
      break;
    }

    let observation = '';
    try {
        switch (action) {
            case 'READ':
                observation = await handleRead(argument);
                break;
            case 'SHELL':
                observation = await handleShell(argument);
                break;
            case 'CODE':
                const [filePath, ...contentParts] = argument.split(':');
                await handleCode(filePath, contentParts.join(':'));
                observation = `Successfully wrote to ${filePath}.`;
                break;
            case 'GIT':
                observation = await handleGit(argument);
                break;
            default:
                observation = `Unknown action: ${action}`;
        }
    } catch (e: any) {
        observation = `Error executing action: ${e.message}`;
    }

    console.log(`> Observation: ${observation.substring(0, 300)}...`); // Truncate long observations
    context.history.push({ action: nextAction, observation });
    console.log('--------------------');
  }
  console.log("Agent loop finished.");
}

program
  .command('run')
  .description('Run the autonomous agent with a specific goal.')
  .argument('<goal>', 'The high-level goal for the agent to achieve.')
  .action(agentLoop);

program.parse(process.argv);
