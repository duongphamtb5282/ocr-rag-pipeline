"""LLM-driven agents for document processing pipeline.

Each agent is a LangGraph node function that:
1. Accepts OCRFormFillState as the sole argument
2. Loads prompts from prompts.registry (not hardcoded strings)
3. Calls the LLM via gateway.service.gateway_call()
4. Returns a dict of state updates
"""
