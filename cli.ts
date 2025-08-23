import { Command } from 'commander';
import { agent } from './agent';

const program = new Command();

program
  .version('1.0.0')
  .description('A CLI for the Consciousness Assessment Framework (CAF)');

program
  .command('assess')
  .description('Assess the consciousness of an AI system')
  .action(async () => {
    await agent.run();
  });

program.parse(process.argv);
