"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const commander_1 = require("commander");
const agent_1 = require("./agent");
const program = new commander_1.Command();
program
    .version('1.0.0')
    .description('A CLI for the Consciousness Assessment Framework (CAF)');
program
    .command('assess')
    .description('Assess the consciousness of an AI system')
    .action(async () => {
    await agent_1.agent.run();
});
program.parse(process.argv);
