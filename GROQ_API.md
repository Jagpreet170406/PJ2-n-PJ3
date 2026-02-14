--- Groq AI Integration Setup Guide -----
What You Get
FREE AI-powered insights and recommendations
500,000 tokens per day (more than enough!)
Smart analysis of your sales data
Natural language recommendations
Graceful fallback to template logic if API unavailable

--- STEPS ----

Step 1: Get Your FREE Groq API Key

1. Go to: [https://console.groq.com](https://console.groq.com)
2. Sign up for a free account (no credit card required!)
3. Navigate to API Keys section
4. Click "Create API Key"
5. Copy your API key (starts with gsk_...)



Step 2: Install Required Package

Commands:
pip install groq

Or install all dependencies:
pip install -r requirements.txt



Step 3: Set Your API Key


Option A: Environment Variable (Recommended)
Windows (Command Prompt):
set GROQ_API_KEY=gsk_your_api_key_here

Windows (PowerShell):
$env:GROQ_API_KEY="gsk_your_api_key_here"

Mac/Linux:
export GROQ_API_KEY=gsk_your_api_key_here


Option B: Create a .env file
Create a file named .env in your project directory:
GROQ_API_KEY=gsk_your_api_key_here

Then install python-dotenv:
pip install python-dotenv
And add to the top of app.py:
from dotenv import load_dotenv
load_dotenv()

Option C: Hardcode (Not Recommended for Production)
In app.py, replace:
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

With:
GROQ_API_KEY = "gsk_your_api_key_here"
Warning: Don’t commit your API key to GitHub!

---

Step 4: Run Your App
python app.py

--- How Groq API Works in Our Project ------
When AI is Available:
1. Dashboard loads your sales data
2. Groq AI analyzes patterns, risks, and opportunities
3. Generates 3 key insights + 5 actionable recommendations
4. Shows in a blue gradient box at the top
5. Template-based insights still shown below for reference

When AI is Unavailable:
* Shows a yellow info banner
* Falls back to template-based recommendations
* Everything still works perfectly

--- Usage Limits (FREE TIER) -------
Tokens per day: 500,000
Requests per minute: 30
Cost: $0 (FREE!)

What This Means:
Each analysis uses approximately 2,000 tokens
You can run about 250 analyses per day
Even with 50 team members checking 5 times daily = 250 uses
You likely won’t hit the limit

--- Troubleshooting ---
“AI insights unavailable” message?

Check:
1. Is your API key set correctly?

Commands: 
import os
print(os.getenv("GROQ_API_KEY"))  # Should print your key

2. Is the groq package installed?

Commands:
pip list | grep groq

3. Check the console for error messages
Rate limit errors?
You’re making too many requests per minute
Wait 60 seconds and try again
Limit is 30 requests per minute

Network/connection errors?
Check your internet connection
Verify Groq API status: [https://status.groq.com](https://status.groq.com)

--- TECHNICAL DETAILS ---
Model Used: llama-3.1-70b-versatile
70 billion parameters
Fast inference (around 100 tokens per second)
Strong for business analysis
No cost

Temperature: 0.3 (consistent, focused responses)
Max Tokens: 1,500 (detailed insights)
Fallback: Automatic graceful degradation

------------- Security Best Practices -------------
DO:
Use environment variables
Add .env to .gitignore
Rotate keys periodically
Keep keys confidential

DON’T:
Hardcode keys in code
Commit keys to GitHub
Share keys publicly
Use keys in client-side code

----------------------------- Need Help ? ----------------------------------------
Groq Documentation: [https://console.groq.com/docs](https://console.groq.com/docs)
Groq Discord: [https://discord.gg/groq](https://discord.gg/groq)


------------------- What's Next? -----------------------------
Once AI insights are working, you can:
1. Customize the AI prompts in generate_ai_insights()
2. Add more sophisticated analysis
3. Create scheduled reports
4. Integrate with email notifications

Enjoy your FREE AI-powered analytics! 🎉


