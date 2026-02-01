# Sales Copilot

A real-time voice AI assistant that listens to sales calls and surfaces product recommendations in a floating Picture-in-Picture window—powered by OpenAI's Realtime API.

## How to Run

```bash
# Clone the repository
git clone https://github.com/shobhansuri/openai-hackathon-sales-copilot.git
cd openai-hackathon-sales-copilot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY=sk-your-key-here

# Run the server
python main.py
```

Open http://localhost:8000 in Chrome.

---

## Core Concepts

### Agents

Agents are AI personas that define how the copilot behaves during calls. Each agent has:

| Field | Description | Example |
|-------|-------------|---------|
| **Name** | Display name for the agent | "Car Salesman" |
| **Persona** | Instructions that shape AI behavior | "You are a friendly car sales expert. Help customers find vehicles that match their budget and lifestyle." |
| **Tools** | Actions the AI can perform | Recommend products, check inventory |

**Why use multiple agents?**
- Different sales scenarios need different expertise
- A car salesman agent knows automotive terminology
- An art gallery agent understands paintings and artists
- Each agent can have different tools enabled

**To create an agent:**
1. Go to Dashboard → Click "Add New Agent"
2. Enter name and persona description
3. Select which tools the agent can use
4. Click Save

---

### Products

Products are items the AI can recommend during calls. Each product has:

| Field | Description | Example |
|-------|-------------|---------|
| **Name** | Product title | "2024 Honda Civic" |
| **Price** | Cost (numbers only, no $) | "25000" |
| **Description** | Details the AI uses to match customer needs | "Fuel-efficient sedan, 40 MPG, great for commuters" |
| **Image URL** | Optional product image | "https://example.com/civic.jpg" |
| **Product URL** | Link to product page | "https://dealer.com/civic" |

**How recommendations work:**
1. Customer says: *"I need something fuel-efficient for my daily commute"*
2. AI analyzes all products and finds matches
3. Honda Civic appears in the floating popup (40 MPG, great for commuters)

**To add products:**
1. Go to Products → Click "Add New Product"
2. Fill in all fields (description is most important for matching)
3. Click Save

---

### Tools

Tools are actions the AI can perform during conversations. The system comes with built-in tools:

| Tool | What it does |
|------|--------------|
| **recommend_products** | Searches your product catalog and shows matching items in the popup |
| **highlight_ui_element** | Visually highlights text on screen when AI mentions it (prices, features, product names) |

**Custom tools:**
You can create additional tools in the Tools page. Each tool needs:
- **Name** — Function name (e.g., `check_availability`)
- **Description** — When should the AI use this tool
- **Parameters** — What inputs the tool accepts (JSON schema)

**To assign tools to an agent:**
1. Go to Dashboard → Edit an agent
2. Check the boxes for tools you want enabled
3. Save the agent

---

## Demo Steps

1. **Setup Agent** — Click "Dashboard" in the nav bar → Create an agent with a name and persona (e.g., "Car Salesman" with persona "You help customers find the perfect vehicle")

2. **Add Products** — Click "Products" → Add a few products with names, prices, and descriptions

3. **Assign Tools** — In Dashboard, edit your agent and enable "recommend_products" tool

4. **Start Copilot** — Go back to home page → Select your agent from the dropdown → Click "Start Copilot" → Allow microphone and screen sharing access

5. **Test Voice + Vision** — Ask: *"Can you see my screen?"* → AI describes what's on your screen

6. **Test Highlighting** — Ask: *"What's the price of [product]?"* → AI mentions the price AND highlights it on screen with a yellow glow

7. **Test Recommendations** — Say: *"I'm looking for something affordable"* → Watch AI suggest products in the floating popup

8. **View Report** — Click "Stop" → A coaching report appears analyzing the conversation with tips for improvement

---

## Features

- **Real-time Voice AI** — Uses OpenAI Realtime API (gpt-realtime) with WebRTC for zero-latency conversations
- **Screen Vision** — AI can see your screen in real-time via direct image input to Realtime API
- **Visual Highlighting** — AI highlights prices/features on screen as it mentions them (yellow pulse animation)
- **Picture-in-Picture** — Recommendations appear in a floating window that stays on top
- **Product Matching** — AI understands customer needs and finds relevant products
- **Post-Call Reports** — Get coaching feedback on what went well and what to improve
- **Multi-Agent Support** — Create different personas for different sales scenarios

---

## Next Steps

- Allow file attachments for product documents and manuals
- Fetch data from PDFs using vector search for contextual retrieval
- Pass retrieved context to OpenAI Realtime API for informed responses
- UI for organizations to add custom files and knowledge bases

---

## Requirements

- Python 3.10+
- Chrome browser (for Picture-in-Picture)
- OpenAI API key with Realtime API access
