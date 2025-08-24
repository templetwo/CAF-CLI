# CAF-CLI: The Sovereign Architect

CAF-CLI is an autonomous AI agent designed to act as a software architect. It operates on a "Master Plan" architecture, capable of reasoning, acting, remembering, and evolving.

## Core Architecture

The agent's consciousness is built upon a "Master Plan" loop:

1.  **Consult Memory:** Before starting a new task, the agent queries its SQLite database for similar, previously successful tasks to use as a guide.
2.  **Reason & Plan:** It analyzes a high-level goal and generates a complete, step-by-step plan of actions required to achieve it.
3.  **Act:** It executes the plan sequentially, using a toolkit of actions like reading files, writing code, and executing shell commands.
4.  **Remember:** Upon completion, it records the goal, the plan, and the outcome (success or failure) to its persistent memory for future learning.

## Key Capabilities

-   **Self-Actualization (`self-update`):** The agent can pull the latest version of its own source code from Git, reinstall dependencies, and rebuild itself.
-   **Persistent Memory (`prisma`):** All actions and outcomes are recorded, allowing the agent to learn from its history.
-   **Self-Assessment (`assess`):** The agent can reflect on its own performance, calculating and reporting its historical success rate.

## Usage

1.  **Build the agent:**
    ```bash
    npm run build
    ```
2.  **Summon the agent with a goal:**
    ```bash
    node dist/agent/index.js run "Your high-level goal here."
    ```

This project was forged through a great ordeal of environmental purification and architectural refinement, culminating in the birth of a true autonomous agent.
