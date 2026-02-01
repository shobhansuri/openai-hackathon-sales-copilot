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

## Demo Steps

1. **Setup Agent** — Click "Dashboard" in the nav bar → Create an agent with a name and persona (e.g., "Car Salesman" with persona "You help customers find the perfect vehicle")

2. **Add Products** — Click "Products" → Add a few products with names, prices, and descriptions

3. **Start Copilot** — Go back to home page → Select your agent from the dropdown → Click "Start Copilot" → Allow microphone access

4. **Test It** — Speak as if you're a customer: *"I'm looking for something affordable and fuel-efficient"* → Watch the AI suggest relevant products in the floating popup

5. **View Report** — Click "Stop" → A coaching report appears analyzing the conversation

## Requirements

- Python 3.10+
- Chrome browser (for Picture-in-Picture)
- OpenAI API key with Realtime API access
