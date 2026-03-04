const { App } = require('@slack/bolt');
const { spawn } = require('child_process');
const WebSocket = require('ws');
const http = require('http');

// Initialize Slack app
const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN,
  port: process.env.PORT || 3000
});

// kagent configuration
const KAGENT_API_URL = process.env.KAGENT_API_URL || 'http://localhost:8081';
const KAGENT_CLI_PATH = process.env.KAGENT_CLI_PATH || '/usr/local/bin/kagent';

// Store active conversations
const activeConversations = new Map();

// Listen for messages mentioning the bot
app.message(async ({ message, say, client }) => {
  try {
    // Skip if message is from bot itself
    if (message.subtype === 'bot_message') return;
    
    // Check if bot is mentioned or it's a DM
    const botUserId = await getBotUserId(client);
    const isDM = message.channel_type === 'im';
    const isMentioned = message.text && message.text.includes(`<@${botUserId}>`);
    
    if (!isDM && !isMentioned) return;
    
    // Extract the actual question (remove bot mention)
    let question = message.text;
    if (isMentioned) {
      question = question.replace(`<@${botUserId}>`, '').trim();
    }
    
    if (!question) {
      await say("Hi! Ask me anything about your Kubernetes cluster. For example: 'What pods are running in the kagent namespace?'");
      return;
    }
    
    // Send "thinking" message
    const thinkingMsg = await say("🤔 Let me check that for you...");
    
    try {
      // Start conversation with kagent
      const response = await startKagentConversation(question, message.user);
      
      // Update the thinking message with the response
      await client.chat.update({
        channel: message.channel,
        ts: thinkingMsg.ts,
        text: response
      });
      
    } catch (error) {
      console.error('Error processing question:', error);
      await client.chat.update({
        channel: message.channel,
        ts: thinkingMsg.ts,
        text: `❌ Sorry, I encountered an error: ${error.message}`
      });
    }
    
  } catch (error) {
    console.error('Error handling message:', error);
  }
});

// Function to get bot user ID
async function getBotUserId(client) {
  try {
    const result = await client.auth.test();
    return result.user_id;
  } catch (error) {
    console.error('Error getting bot user ID:', error);
    throw error;
  }
}

// Function to start conversation with kagent
async function startKagentConversation(question, userId) {
  return new Promise((resolve, reject) => {
    // Use kagent CLI with the question
    const kagentProcess = spawn(KAGENT_CLI_PATH, [
      'chat',
      '--endpoint', KAGENT_API_URL,
      '--user-id', `slack-${userId}`,
      '--team', 'k8s-agent',
      '--message', question
    ]);
    
    let output = '';
    let errorOutput = '';
    
    kagentProcess.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    kagentProcess.stderr.on('data', (data) => {
      errorOutput += data.toString();
    });
    
    kagentProcess.on('close', (code) => {
      if (code === 0) {
        // Clean up the output (remove CLI formatting)
        const cleanOutput = cleanKagentOutput(output);
        resolve(cleanOutput || 'I completed your request, but got no response.');
      } else {
        reject(new Error(`kagent CLI failed: ${errorOutput || 'Unknown error'}`));
      }
    });
    
    kagentProcess.on('error', (error) => {
      reject(new Error(`Failed to start kagent CLI: ${error.message}`));
    });
    
    // Set timeout
    setTimeout(() => {
      kagentProcess.kill();
      reject(new Error('Request timed out'));
    }, 60000); // 60 second timeout
  });
}

// Function to clean kagent CLI output for Slack
function cleanKagentOutput(output) {
  // Remove ANSI color codes
  let cleaned = output.replace(/\x1b\[[0-9;]*m/g, '');
  
  // Remove CLI prompts and formatting
  cleaned = cleaned.replace(/^.*?> /gm, '');
  cleaned = cleaned.replace(/^kagent.*$/gm, '');
  cleaned = cleaned.replace(/^Connecting to.*$/gm, '');
  cleaned = cleaned.replace(/^Session created.*$/gm, '');
  
  // Clean up extra whitespace
  cleaned = cleaned.replace(/\n\s*\n/g, '\n').trim();
  
  // Format for Slack (add code blocks for command outputs)
  if (cleaned.includes('kubectl') || cleaned.includes('NAME') || cleaned.includes('READY')) {
    cleaned = '```\n' + cleaned + '\n```';
  }
  
  return cleaned;
}

// Create a separate HTTP server for health checks
const healthServer = http.createServer((req, res) => {
  if (req.url === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'healthy' }));
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
  }
});

// Start the app
(async () => {
  try {
    await app.start();
    console.log('⚡️ Kagent Slack bot is running!');
    console.log(`📡 Connecting to kagent at: ${KAGENT_API_URL}`);
    console.log(`🔧 Using kagent CLI at: ${KAGENT_CLI_PATH}`);
    
    // Start health check server
    const port = process.env.PORT || 3000;
    healthServer.listen(port, () => {
      console.log(`🏥 Health check server running on port ${port}`);
    });
    
  } catch (error) {
    console.error('Failed to start Slack bot:', error);
    process.exit(1);
  }
})(); 