# Python to C++ Code Converter

Converts Python code into fast, optimized C++ using an LLM of your choice. The tool inspects your machine's OS, CPU, and installed toolchain and feeds that context to the model so the generated C++ (and compile flags) are tailored to your specific system. Output is written to `main.cpp`, ready to compile and run.

## How it works

1. `system_info.py` collects details about your machine, OS, CPU brand, core count, SIMD support, installed compilers and build tools.
2. This system info, plus your Python code, is sent to the selected LLM with instructions to port it to the fastest possible C++.
3. The model's C++ response is written to `main.cpp`.
4. A **Gradio** web interface lets you paste Python code, pick a model, and generate the C++ version in one click.

## Built with

- Python
- Gradio
- OpenAI-compatible chat completions API (used to call every provider below)
- python-dotenv
- Supported models: OpenAI (GPT-5), Anthropic (Claude), Google (Gemini), Grok, Groq, OpenRouter, and local models via Ollama

## To run it

1. Install the required Python packages:
   - openai
   - python dotenv
   - gradio
2. Create a `.env` file with the API key(s) for whichever model(s) you plan to use:
   - OPENAI_API_KEY
   - ANTHROPIC_API_KEY
   - GOOGLE_API_KEY
   - GROK_API_KEY
   - GROQ_API_KEY
   - OPENROUTER_API_KEY
3. (Optional) For local models — `qwen2.5-coder`, `deepseek-coder-v2`, `gpt-oss:20b` — install and run [Ollama](https://ollama.com).
4. To use available models from `Hugging-face`, its API-Key needs to be set too.

5. In the Gradio UI, paste Python code (or use the included π-approximation example), choose a model, and click **Convert code**.

**Output:** The generated C++ is displayed in the interface and saved to `main.cpp`.
