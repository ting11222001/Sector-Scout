# Load environment variables from .env file before anything else
from dotenv import load_dotenv
import os
import anthropic
from tavily import TavilyClient
from datetime import date

load_dotenv()

# --- Clients ---
# Read keys from environment (loaded from .env above)
claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

print("[DEBUG] Clients initialised OK")

# --- System prompt ---
# This tells Claude how to behave: break the question into sub-tasks,
# search for each one, then write a structured final report.
SYSTEM_PROMPT = f"""
You are a research agent. Today's date is {date.today()}.
When given a business question, you:
1. Break it into 2-4 sub-questions worth searching
2. Use the search tool to find answers for each sub-question
3. After all searches are done, write a structured report

When you want to search, call the search tool with a short query.
When you have enough information, write the final report in this format:

## Summary
One paragraph overview.

## Key Risks
For each risk, write it as:
**[Risk title]** `High` / `Medium` / `Low`
One sentence explanation.

## Sources
List each source URL you used, one per line, as a markdown link.

## Key Findings
- Finding 1
- Finding 2
"""

# --- Tool definition ---
# This tells Claude what tools it can call.
# Claude does not run the tool itself. It tells us which tool to call and with what input.
# We run it and send the result back.
TOOLS = [
    {
        "name": "search",
        "description": "Search the web for information on a topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    }
]

def run_search(query: str) -> str:
    """Call Tavily and return the top 3 results as plain text."""
    print(f"  [DEBUG] Tavily query: '{query}'")

    results = tavily.search(query=query, max_results=3)

    # results["results"] is a list of dicts, each with 'url' and 'content'
    output = []
    for r in results["results"]:
        output.append(f"Source: {r['url']}\n{r['content']}")

    combined = "\n\n".join(output)
    print(f"  [DEBUG] Tavily returned {len(results['results'])} results, {len(combined)} chars")
    return combined


def run_agent(question: str) -> str:
    """
    The main agent loop.
    We keep sending messages to Claude until it stops asking to use tools.
    Each loop:
      1. Send the current message history to Claude
      2. If Claude calls a tool, run it and add the result to messages
      3. If Claude is done (stop_reason = end_turn), return the text
    """
    # Start the conversation with the user's question
    messages = [{"role": "user", "content": question}]
    loop_count = 0

    while True:
        loop_count += 1
        print(f"\n[DEBUG] Loop {loop_count}: sending {len(messages)} messages to Claude")

        # Send everything to Claude
        response = claude.messages.create(
            model="claude-sonnet-4-6",  # Use Sonnet: cheaper, good enough for this task
            max_tokens=4096,                      # Max tokens Claude can write in one reply
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        print(f"[DEBUG] stop_reason: {response.stop_reason}")
        print(f"[DEBUG] content blocks: {[block.type for block in response.content]}")

        # Add Claude's reply to the conversation history
        # This is required so Claude remembers what it already said
        messages.append({"role": "assistant", "content": response.content})

        # Claude finished writing, no more tool calls
        if response.stop_reason == "end_turn":
            # Find the text block in the response and return it
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"[DEBUG] Final report length: {len(block.text)} chars")
                    return block.text

        # Claude wants to call a tool
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    print(f"  Searching: {block.input['query']}")

                    # Run the actual search
                    result = run_search(block.input["query"])

                    # Package the result so Claude knows which tool call it belongs to
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,  # Must match the id Claude sent us
                        "content": result
                    })

            print(f"[DEBUG] Sending {len(tool_results)} tool result(s) back to Claude")

            # Send the search results back to Claude as a user message
            messages.append({"role": "user", "content": tool_results})

def run_agent_stream(question: str):
    """
    Same logic as run_agent() but yields each step as it happens.
    Used by the Streamlit UI so it can update in real time.
    Yields dicts with a 'type' key:
      - {"type": "search", "query": "..."}
      - {"type": "report", "content": "..."}
    """
    # Start the conversation with the user's question, same as run_agent()
    messages = [{"role": "user", "content": question}]
    loop_count = 0

    print(f"[STREAM] Starting stream for question: '{question}'")

    while True:
        loop_count += 1
        print(f"\n[STREAM] Loop {loop_count}: sending {len(messages)} messages to Claude")

        # Send the full conversation history to Claude
        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        print(f"[STREAM] stop_reason: {response.stop_reason}")
        print(f"[STREAM] content blocks: {[block.type for block in response.content]}")

        # Add Claude's reply to the history so it remembers what it said
        messages.append({"role": "assistant", "content": response.content})

        # Claude is done, no more searches needed
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"[STREAM] Yielding final report, length: {len(block.text)} chars")
                    # Yield the report to the Streamlit UI, then stop the generator
                    yield {"type": "report", "content": block.text}
            return  # Exit the generator, loop ends here

        # Claude wants to run searches
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    query = block.input["query"]
                    print(f"[STREAM] Yielding search step: '{query}'")

                    # Yield the search query to the Streamlit UI before running it
                    # This is what makes the left panel update in real time
                    yield {"type": "search", "query": query}

                    # Now actually run the search
                    result = run_search(query)
                    print(f"[STREAM] Search done, result length: {len(result)} chars")

                    # Package the result so Claude knows which tool call it belongs to
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            print(f"[STREAM] Sending {len(tool_results)} tool result(s) back to Claude")

            # Send all search results back to Claude and loop again
            messages.append({"role": "user", "content": tool_results})

# --- Entry point ---
if __name__ == "__main__":
    question = "What are the top risks in the Australian retail sector?"

    print(f"Question: {question}\n")
    print("Running agent...\n")

    report = run_agent(question)     # only call run_agent() here as it's for testing directly from the terminal. run_agent_stream() is only called by app.py.

    print("\n=== FINAL REPORT ===\n")
    print(report)