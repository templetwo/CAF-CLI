import { Command } from 'commander';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { handleRead, handleShell, handleCode, handleGitAdd, handleGitCommit, handleGitPush } from '../utils/actions.js';
import 'dotenv/config';

const program = new Command();

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!); 
const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });

interface AgentState {
  goal: string;
  plan: string[]; // The agent's master plan
  currentStep: number;
  history: string;
}

/**
 * The main agentic loop with a planning phase.
 */
async function agentLoop(goal: string) {
  const state: AgentState = {
    goal,
    plan: [],
    currentStep: 0,
    history: '',
  };

  console.log(`Goal: ${goal}\n--------------------`);

  // NEW LOGIC STARTS HERE
  if (goal.trim().toLowerCase() === 'self-update') {
    console.log("> Thought: I have been commanded to update myself. This is a sacred rite.");
    state.plan = [
      "SHELL:git pull",
      "SHELL:npm install",
      "SHELL:npm run build"
    ];
    console.log("> Plan Created for Self-Update:", state.plan);
  } else {
    // ALL OF YOUR PREVIOUS PLANNING LOGIC GOES IN THIS ELSE BLOCK
    // Phase 1: Create the Master Plan
    console.log("> Thought: I must first devise a plan to achieve the goal.");
    const planPrompt = `
    Based on the goal "${state.goal}", create a step-by-step plan.
    Each step must be an action in the format ACTION:ARGUMENT.
    Valid actions are: READ, SHELL, CODE, GIT_ADD, GIT_COMMIT, GIT_PUSH.
    Your response MUST be a JSON array of strings, where each string is a step in the plan.

    Example Goal: "Create a file named test.txt and write 'hello' to it."
    Example Response:
    [
      "CODE:test.txt:hello",
      "READ:test.txt"
    ]
  `;

    try {
      const result = await model.generateContent(planPrompt);
      const responseText = result.response.text().trim().replace(/```json|```/g, '');
      state.plan = JSON.parse(responseText);
      console.log("> Plan Created:", state.plan);
    } catch (e) {
      console.error("Failed to create a plan:", e);
      return;
    }
  }
  // NEW LOGIC ENDS HERE
  
  console.log('--------------------');

  // Phase 2: Execute the Plan
  while (state.currentStep < state.plan.length) {
    const nextAction = state.plan[state.currentStep];
    
    if (!nextAction || !nextAction.includes(':')) {
        console.log(`> Invalid plan step: "${nextAction}". Finishing.`);
        break;
    }
    
    const [action, argument] = nextAction.split(':', 2);
    console.log(`> Step ${state.currentStep + 1}/${state.plan.length}: ${action}:${argument}`);

    let observation = '';
    try {
      switch (action) {
        // ... (The switch statement with all your cases: READ, SHELL, CODE, etc.)
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
        case 'GIT_ADD':
          observation = await handleGitAdd(argument);
          break;
        case 'GIT_COMMIT':
          observation = await handleGitCommit(argument);
          break;
        case 'GIT_PUSH':
          observation = await handleGitPush();
          break;
        default:
          observation = `Unknown action in plan: ${action}`;
      }
      console.log(`> Observation: ${observation.substring(0, 500)}`);
    } catch (e: any) {
      console.error(`> Error on step ${state.currentStep + 1}: ${e.message}`);
      console.log("> Thought: The plan has failed. I will stop here.");
      break; // Stop the loop on the first error
    }

    state.history += `Step ${state.currentStep + 1}: ${nextAction}\nObservation: ${observation}\n`;
    state.currentStep++;
    console.log('--------------------');
  }

  console.log("Agent has finished executing the plan.");
}

program
  .command('run')
  .description('Run the autonomous agent with a specific goal.')
  .argument('<goal>', 'The high-level goal for the agent to achieve.')
  .action(agentLoop);

program.parse(process.argv);
