"""
python_to_cpp.py

Gradio app that ports a Python snippet to high performance C++ using an
LLM of your choice. The generated code is written to main.cpp, ready to
be compiled with the command shown in `compile_command`.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
from system_info import retrieve_system_info

load_dotenv(override=True)
openai_api_key = os.getenv('OPENAI_API_KEY')
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
google_api_key = os.getenv('GOOGLE_API_KEY')
grok_api_key = os.getenv('GROK_API_KEY')
groq_api_key = os.getenv('GROQ_API_KEY')
openrouter_api_key = os.getenv('OPENROUTER_API_KEY')


if openai_api_key:
    print(f"OpenAI API Key exists and begins {openai_api_key[:8]}")
else:
    print("OpenAI API Key not set")

if anthropic_api_key:
    print(f"Anthropic API Key exists and begins {anthropic_api_key[:7]}")
else:
    print("Anthropic API Key not set (and this is optional)")

if google_api_key:
    print(f"Google API Key exists and begins {google_api_key[:2]}")
else:
    print("Google API Key not set (and this is optional)")

if grok_api_key:
    print(f"Grok API Key exists and begins {grok_api_key[:4]}")
else:
    print("Grok API Key not set (and this is optional)")

if groq_api_key:
    print(f"Groq API Key exists and begins {groq_api_key[:4]}")
else:
    print("Groq API Key not set (and this is optional)")

if openrouter_api_key:
    print(f"OpenRouter API Key exists and begins {openrouter_api_key[:6]}")
else:
    print("OpenRouter API Key not set (and this is optional)")

# model clients
openai = OpenAI()

anthropic_url = "https://api.anthropic.com/v1/"
gemini_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
grok_url = "https://api.x.ai/v1"
groq_url = "https://api.groq.com/openai/v1"
ollama_url = "http://localhost:11434/v1"
openrouter_url = "https://openrouter.ai/api/v1"

anthropic = OpenAI(api_key=anthropic_api_key or "not-set", base_url=anthropic_url)
gemini = OpenAI(api_key=google_api_key or "not-set", base_url=gemini_url)
grok = OpenAI(api_key=grok_api_key or "not-set", base_url=grok_url)
groq = OpenAI(api_key=groq_api_key or "not-set", base_url=groq_url)
ollama = OpenAI(api_key="ollama", base_url=ollama_url)
openrouter = OpenAI(api_key=openrouter_api_key or "not-set", base_url=openrouter_url)

# Model selection
models = [
    "gpt-5",
    "claude-sonnet-4-5-20250929",
    "grok-4",
    "gemini-2.5-pro",
    "qwen2.5-coder",
    "deepseek-coder-v2",
    "gpt-oss:20b",
    "qwen/qwen3-coder-30b-a3b-instruct",
    "openai/gpt-oss-120b",
]

clients = {
    "gpt-5": openai,
    "claude-sonnet-4-5-20250929": anthropic,
    "grok-4": grok,
    "gemini-2.5-pro": gemini,
    "openai/gpt-oss-120b": groq,
    "qwen2.5-coder": ollama,
    "deepseek-coder-v2": ollama,
    "gpt-oss:20b": ollama,
    "qwen/qwen3-coder-30b-a3b-instruct": openrouter,
}


# system context
system_info = retrieve_system_info()
compile_command = [
    "clang++", "-std=c++17", "-Ofast", "-mcpu=native",
    "-flto=thin", "-fvisibility=hidden", "-DNDEBUG", "main.cpp", "-o", "main",
]
run_command = ["./main"]

system_prompt = """
Your task is to convert Python code into high performance C++ code.
Respond only with C++ code. Do not provide any explanation other than occasional comments.
The C++ response needs to produce an identical output in the fastest possible time.
"""

def user_prompt_for(python):
    """Build the user prompt: the source code plus system/compile context."""
    return f"""
Port this Python code to C++ with the fastest possible implementation that produces identical output in the least time.
The system information is:
{system_info}
Your response will be written to a file called main.cpp and then compiled and executed; the compilation command is:
{compile_command}
Respond only with C++ code.
Python code to port:

```python
{python}
```
"""

def messages_for(python):
    """Assemble the chat messages sent to the model."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt_for(python)}
    ]

def write_output(cpp):
    """Save the generated C++ code to main.cpp."""
    with open("main.cpp", "w") as f:
        f.write(cpp)

def port(model, python):
    """Send the Python code to the selected model and return the C++ port."""
    client = clients[model]
    openai_reasoning_models = {"gpt-5"}
    reasoning_effort = "high" if model in openai_reasoning_models else None
    response = client.chat.completions.create(
        model=model, messages=messages_for(python), reasoning_effort=reasoning_effort
    )
    reply = response.choices[0].message.content
    reply = reply.replace('```cpp', '').replace('```', '')  # strip markdown fences
    write_output(reply)
    return reply

# Default Python snippet 
pi = """
import time

def calculate(iterations, param1, param2):
    result = 1.0
    for i in range(1, iterations+1):
        j = i * param1 - param2
        result -= (1/j)
        j = i * param1 + param2
        result += (1/j)
    return result

start_time = time.time()
result = calculate(200_000_000, 4, 1) * 4
end_time = time.time()

print(f"Result: {result:.12f}")
print(f"Execution Time: {(end_time - start_time):.6f} seconds")
"""

# interface
with gr.Blocks() as ui:
    with gr.Row():
        python = gr.Textbox(label="Python code:", lines=28, value=pi)
        cpp = gr.Textbox(label="C++ code:", lines=28)
    with gr.Row():
        model = gr.Dropdown(models, label="Select model", value=models[0])
        convert = gr.Button("Convert code")

    convert.click(port, inputs=[model, python], outputs=[cpp])

ui.launch(inbrowser=True)
