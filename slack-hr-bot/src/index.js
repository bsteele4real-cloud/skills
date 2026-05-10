const { App } = require("@slack/bolt");
const { ElevenLabsClient } = require("@elevenlabs/elevenlabs-js");
const express = require("express");

require("dotenv").config();

const elevenlabs = new ElevenLabsClient({
  apiKey: process.env.ELEVENLABS_API_KEY,
});

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN,
});

const HR_AGENT_ID = process.env.HR_AGENT_ID;

const conversationStore = new Map();

async function getOrCreateConversation(userId, slackUserInfo) {
  let session = conversationStore.get(userId);

  if (session && Date.now() - session.lastActive < 30 * 60 * 1000) {
    session.lastActive = Date.now();
    return session;
  }

  const signedUrl = await elevenlabs.conversationalAi.conversations.getSignedUrl({
    agentId: HR_AGENT_ID,
  });

  session = {
    signedUrl: signedUrl.signed_url,
    conversationId: null,
    lastActive: Date.now(),
    userInfo: slackUserInfo,
    messages: [],
  };

  conversationStore.set(userId, session);
  return session;
}

async function sendToAgent(session, userMessage) {
  const response = await fetch("https://api.elevenlabs.io/v1/convai/conversation/text", {
    method: "POST",
    headers: {
      "xi-api-key": process.env.ELEVENLABS_API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      agent_id: HR_AGENT_ID,
      conversation_id: session.conversationId,
      text: userMessage,
      user_id: session.userInfo?.id,
    }),
  });

  const data = await response.json();

  if (!session.conversationId && data.conversation_id) {
    session.conversationId = data.conversation_id;
  }

  session.messages.push(
    { role: "user", content: userMessage },
    { role: "assistant", content: data.response }
  );

  return data.response;
}

app.message(async ({ message, client, say }) => {
  if (message.subtype || message.bot_id) return;
  if (message.channel_type !== "im") return;

  try {
    const userInfo = await client.users.info({ user: message.user });
    const session = await getOrCreateConversation(message.user, userInfo.user);

    await client.reactions.add({
      channel: message.channel,
      timestamp: message.ts,
      name: "hourglass_flowing_sand",
    });

    const response = await sendToAgent(session, message.text);

    await client.reactions.remove({
      channel: message.channel,
      timestamp: message.ts,
      name: "hourglass_flowing_sand",
    });

    await say({
      text: response,
      blocks: formatResponseBlocks(response),
    });
  } catch (error) {
    console.error("Error handling message:", error);
    await say("I'm sorry, I encountered an issue. Please try again or contact HR directly.");
  }
});

app.event("app_mention", async ({ event, client, say }) => {
  const text = event.text.replace(/<@[A-Z0-9]+>/g, "").trim();

  if (!text) {
    await say({
      text: "Hi! I'm the HR assistant. You can ask me about PTO, benefits, company policies, and more. Send me a direct message for private questions!",
      thread_ts: event.ts,
    });
    return;
  }

  try {
    const userInfo = await client.users.info({ user: event.user });
    const session = await getOrCreateConversation(event.user, userInfo.user);

    const response = await sendToAgent(session, text);

    await say({
      text: response,
      thread_ts: event.ts,
    });
  } catch (error) {
    console.error("Error handling mention:", error);
    await say({
      text: "I'm sorry, I encountered an issue. Please try again.",
      thread_ts: event.ts,
    });
  }
});

app.command("/hr", async ({ command, ack, respond }) => {
  await ack();

  if (!command.text) {
    await respond({
      text: "How can I help? Try `/hr What's the PTO policy?` or `/hr How do I request time off?`",
      response_type: "ephemeral",
    });
    return;
  }

  try {
    const session = await getOrCreateConversation(command.user_id, { id: command.user_id });
    const response = await sendToAgent(session, command.text);

    await respond({
      text: response,
      blocks: formatResponseBlocks(response),
      response_type: "ephemeral",
    });
  } catch (error) {
    console.error("Error handling /hr command:", error);
    await respond({
      text: "I'm sorry, I encountered an issue. Please try again.",
      response_type: "ephemeral",
    });
  }
});

app.command("/pto", async ({ command, ack, client, respond }) => {
  await ack();

  const args = command.text.toLowerCase().trim();

  if (!args || args === "balance" || args === "check") {
    const session = await getOrCreateConversation(command.user_id, { id: command.user_id });
    const response = await sendToAgent(session, "What is my PTO balance?");
    await respond({ text: response, response_type: "ephemeral" });
    return;
  }

  if (args === "request" || args === "new") {
    await client.views.open({
      trigger_id: command.trigger_id,
      view: {
        type: "modal",
        callback_id: "pto_request_modal",
        title: { type: "plain_text", text: "Request Time Off" },
        submit: { type: "plain_text", text: "Submit Request" },
        close: { type: "plain_text", text: "Cancel" },
        blocks: [
          {
            type: "input",
            block_id: "start_date_block",
            element: {
              type: "datepicker",
              action_id: "start_date",
              placeholder: { type: "plain_text", text: "Select start date" },
            },
            label: { type: "plain_text", text: "Start Date" },
          },
          {
            type: "input",
            block_id: "end_date_block",
            element: {
              type: "datepicker",
              action_id: "end_date",
              placeholder: { type: "plain_text", text: "Select end date" },
            },
            label: { type: "plain_text", text: "End Date" },
          },
          {
            type: "input",
            block_id: "pto_type_block",
            element: {
              type: "static_select",
              action_id: "pto_type",
              placeholder: { type: "plain_text", text: "Select type" },
              options: [
                { text: { type: "plain_text", text: "Vacation" }, value: "vacation" },
                { text: { type: "plain_text", text: "Sick Leave" }, value: "sick" },
                { text: { type: "plain_text", text: "Personal" }, value: "personal" },
              ],
            },
            label: { type: "plain_text", text: "Type" },
          },
          {
            type: "input",
            block_id: "reason_block",
            optional: true,
            element: {
              type: "plain_text_input",
              action_id: "reason",
              multiline: true,
              placeholder: { type: "plain_text", text: "Optional: Add a note" },
            },
            label: { type: "plain_text", text: "Notes" },
          },
        ],
      },
    });
    return;
  }

  const session = await getOrCreateConversation(command.user_id, { id: command.user_id });
  const response = await sendToAgent(session, `PTO request: ${command.text}`);
  await respond({ text: response, response_type: "ephemeral" });
});

app.view("pto_request_modal", async ({ ack, body, view, client }) => {
  await ack();

  const values = view.state.values;
  const startDate = values.start_date_block.start_date.selected_date;
  const endDate = values.end_date_block.end_date.selected_date;
  const ptoType = values.pto_type_block.pto_type.selected_option.value;
  const reason = values.reason_block.reason?.value || "";

  const userId = body.user.id;
  const session = await getOrCreateConversation(userId, { id: userId });

  const message = `Submit a PTO request: ${ptoType} from ${startDate} to ${endDate}${reason ? `. Notes: ${reason}` : ""}`;
  const response = await sendToAgent(session, message);

  await client.chat.postMessage({
    channel: userId,
    text: response,
    blocks: [
      {
        type: "section",
        text: { type: "mrkdwn", text: `*PTO Request Submitted*\n${response}` },
      },
      {
        type: "context",
        elements: [
          {
            type: "mrkdwn",
            text: `Type: ${ptoType} | Dates: ${startDate} to ${endDate}`,
          },
        ],
      },
    ],
  });
});

app.command("/benefits", async ({ command, ack, respond }) => {
  await ack();

  const query = command.text || "all my benefits";
  const session = await getOrCreateConversation(command.user_id, { id: command.user_id });
  const response = await sendToAgent(session, `Tell me about ${query}`);

  await respond({
    text: response,
    blocks: formatResponseBlocks(response),
    response_type: "ephemeral",
  });
});

app.command("/policy", async ({ command, ack, respond }) => {
  await ack();

  if (!command.text) {
    await respond({
      text: "Please specify a policy topic. Example: `/policy remote work` or `/policy dress code`",
      response_type: "ephemeral",
    });
    return;
  }

  const session = await getOrCreateConversation(command.user_id, { id: command.user_id });
  const response = await sendToAgent(session, `What is the company policy on ${command.text}?`);

  await respond({
    text: response,
    blocks: formatResponseBlocks(response),
    response_type: "ephemeral",
  });
});

app.event("app_home_opened", async ({ event, client }) => {
  await client.views.publish({
    user_id: event.user,
    view: {
      type: "home",
      blocks: [
        {
          type: "header",
          text: { type: "plain_text", text: "HR Assistant" },
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: "Welcome! I'm here to help with your HR questions. Here's what I can help with:",
          },
        },
        { type: "divider" },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: "*PTO & Time Off*\nCheck your balance, request time off, or view pending requests.",
          },
          accessory: {
            type: "button",
            text: { type: "plain_text", text: "Check PTO" },
            action_id: "check_pto_balance",
          },
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: "*Benefits*\nLearn about health insurance, 401k, and other benefits.",
          },
          accessory: {
            type: "button",
            text: { type: "plain_text", text: "View Benefits" },
            action_id: "view_benefits",
          },
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: "*Company Policies*\nSearch our policy handbook for answers.",
          },
          accessory: {
            type: "button",
            text: { type: "plain_text", text: "Search Policies" },
            action_id: "search_policies",
          },
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: "*Contact HR*\nNeed to speak with someone directly? Get in touch with the HR team.",
          },
          accessory: {
            type: "button",
            text: { type: "plain_text", text: "Contact HR" },
            action_id: "contact_hr",
          },
        },
        { type: "divider" },
        {
          type: "context",
          elements: [
            {
              type: "mrkdwn",
              text: "Send me a direct message anytime with your HR questions!",
            },
          ],
        },
      ],
    },
  });
});

app.action("check_pto_balance", async ({ ack, body, client }) => {
  await ack();
  const session = await getOrCreateConversation(body.user.id, { id: body.user.id });
  const response = await sendToAgent(session, "What is my PTO balance?");
  await client.chat.postMessage({
    channel: body.user.id,
    text: response,
  });
});

app.action("view_benefits", async ({ ack, body, client }) => {
  await ack();
  const session = await getOrCreateConversation(body.user.id, { id: body.user.id });
  const response = await sendToAgent(session, "Give me an overview of all my benefits");
  await client.chat.postMessage({
    channel: body.user.id,
    text: response,
  });
});

app.action("search_policies", async ({ ack, body, client }) => {
  await ack();
  await client.views.open({
    trigger_id: body.trigger_id,
    view: {
      type: "modal",
      callback_id: "policy_search_modal",
      title: { type: "plain_text", text: "Search Policies" },
      submit: { type: "plain_text", text: "Search" },
      blocks: [
        {
          type: "input",
          block_id: "search_query_block",
          element: {
            type: "plain_text_input",
            action_id: "search_query",
            placeholder: { type: "plain_text", text: "e.g., remote work, dress code, expenses" },
          },
          label: { type: "plain_text", text: "What policy are you looking for?" },
        },
      ],
    },
  });
});

app.view("policy_search_modal", async ({ ack, body, view, client }) => {
  await ack();
  const query = view.state.values.search_query_block.search_query.value;
  const userId = body.user.id;
  const session = await getOrCreateConversation(userId, { id: userId });
  const response = await sendToAgent(session, `What is the company policy on ${query}?`);
  await client.chat.postMessage({
    channel: userId,
    text: response,
  });
});

app.action("contact_hr", async ({ ack, body, client }) => {
  await ack();
  const session = await getOrCreateConversation(body.user.id, { id: body.user.id });
  const response = await sendToAgent(
    session,
    "I need to speak with someone from HR directly. How can I contact them?"
  );
  await client.chat.postMessage({
    channel: body.user.id,
    text: response,
  });
});

function formatResponseBlocks(text) {
  const blocks = [];

  blocks.push({
    type: "section",
    text: { type: "mrkdwn", text },
  });

  if (text.toLowerCase().includes("pto") || text.toLowerCase().includes("time off")) {
    blocks.push({
      type: "actions",
      elements: [
        {
          type: "button",
          text: { type: "plain_text", text: "Request Time Off" },
          action_id: "open_pto_modal",
          style: "primary",
        },
        {
          type: "button",
          text: { type: "plain_text", text: "Check Balance" },
          action_id: "check_pto_balance",
        },
      ],
    });
  }

  return blocks;
}

app.action("open_pto_modal", async ({ ack, body, client }) => {
  await ack();
  await client.views.open({
    trigger_id: body.trigger_id,
    view: {
      type: "modal",
      callback_id: "pto_request_modal",
      title: { type: "plain_text", text: "Request Time Off" },
      submit: { type: "plain_text", text: "Submit Request" },
      close: { type: "plain_text", text: "Cancel" },
      blocks: [
        {
          type: "input",
          block_id: "start_date_block",
          element: {
            type: "datepicker",
            action_id: "start_date",
          },
          label: { type: "plain_text", text: "Start Date" },
        },
        {
          type: "input",
          block_id: "end_date_block",
          element: {
            type: "datepicker",
            action_id: "end_date",
          },
          label: { type: "plain_text", text: "End Date" },
        },
        {
          type: "input",
          block_id: "pto_type_block",
          element: {
            type: "static_select",
            action_id: "pto_type",
            options: [
              { text: { type: "plain_text", text: "Vacation" }, value: "vacation" },
              { text: { type: "plain_text", text: "Sick Leave" }, value: "sick" },
              { text: { type: "plain_text", text: "Personal" }, value: "personal" },
            ],
          },
          label: { type: "plain_text", text: "Type" },
        },
        {
          type: "input",
          block_id: "reason_block",
          optional: true,
          element: {
            type: "plain_text_input",
            action_id: "reason",
            multiline: true,
          },
          label: { type: "plain_text", text: "Notes" },
        },
      ],
    },
  });
});

setInterval(() => {
  const thirtyMinutesAgo = Date.now() - 30 * 60 * 1000;
  for (const [userId, session] of conversationStore.entries()) {
    if (session.lastActive < thirtyMinutesAgo) {
      conversationStore.delete(userId);
    }
  }
}, 5 * 60 * 1000);

(async () => {
  await app.start();
  console.log("HR Bot is running!");
})();
