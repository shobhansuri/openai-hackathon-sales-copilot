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

Tools are actions the AI can perform during conversations. The system comes with a built-in tool:

| Tool | What it does |
|------|--------------|
| **recommend_products** | Searches your product catalog and shows matching items in the popup |

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

4. **Start Copilot** — Go back to home page → Select your agent from the dropdown → Click "Start Copilot" → Allow microphone access

5. **Test It** — Speak as if you're a customer: *"I'm looking for something affordable and fuel-efficient"* → Watch the AI suggest relevant products in the floating popup

6. **View Report** — Click "Stop" → A coaching report appears analyzing the conversation with tips for improvement

---

## Features

- **Real-time Voice AI** — Uses OpenAI Realtime API with WebRTC for zero-latency conversations
- **Picture-in-Picture** — Recommendations appear in a floating window that stays on top
- **Product Matching** — AI understands customer needs and finds relevant products
- **Post-Call Reports** — Get coaching feedback on what went well and what to improve
- **Multi-Agent Support** — Create different personas for different sales scenarios

---

## Requirements

- Python 3.10+
- Chrome browser (for Picture-in-Picture)
- OpenAI API key with Realtime API access
