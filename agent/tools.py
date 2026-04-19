"""Pluggable tool registry for the 0g Mem agent runtime."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import requests


# ---------------------------------------------------------------------------
# Tool Result
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Result returned by a tool after execution."""
    tool: str
    input: dict
    output: str
    success: bool
    latency_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "input": self.input,
            "output": self.output,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Tool Definition
# ---------------------------------------------------------------------------

@dataclass
class ToolDef:
    """Definition of a tool — name, description, parameter schema, handler."""
    name: str
    description: str
    input_schema: dict          # JSON Schema for the tool's input
    handler: Callable[..., Awaitable[ToolResult]]
    timeout_seconds: int = 30


# ---------------------------------------------------------------------------
# Web Search Tool (MVP — DuckDuckGo HTML, no API key required)
# ---------------------------------------------------------------------------

async def _web_search_impl(query: str, num_results: int = 5) -> ToolResult:
    """Search the web via DuckDuckGo HTML (no API key required for MVP)."""
    start = time.time()
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        params = {"q": query, "kl": "wt-wt"}
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params=params,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()

        # Extract text snippets from results
        html = resp.text
        results: list[str] = []
        # Match <a class="result__a" href="...">Title Text</a>
        for match in re.finditer(r'<a class="result__a"[^>]*>(.*?)</a>', html):
            title = re.sub(r'<[^>]+>', "", match.group(1)).strip()
            if title and title not in results:
                results.append(title)
            if len(results) >= num_results:
                break

        if not results:
            output = f"No results found for: {query}"
        else:
            lines = [f"{i+1}. {r}" for i, r in enumerate(results)]
            output = f"Search results for '{query}':\n" + "\n".join(lines)

        return ToolResult(
            tool="web_search",
            input={"query": query, "num_results": num_results},
            output=output,
            success=True,
            latency_ms=int((time.time() - start) * 1000),
        )
    except Exception as exc:
        return ToolResult(
            tool="web_search",
            input={"query": query, "num_results": num_results},
            output="",
            success=False,
            latency_ms=int((time.time() - start) * 1000),
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Tavily Search Tool (requires Tavily API key — set TAVILY_API_KEY env var)
# ---------------------------------------------------------------------------

async def _tavily_search_impl(query: str, num_results: int = 5) -> ToolResult:
    """Search the web via Tavily API (requires TAVILY_API_KEY env var)."""
    import os
    start = time.time()
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return ToolResult(
            tool="tavily_search",
            input={"query": query, "num_results": num_results},
            output="",
            success=False,
            latency_ms=int((time.time() - start) * 1000),
            error="TAVILY_API_KEY not set in environment",
        )
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={
                "api_key": api_key,
                "query": query,
                "max_results": num_results,
                "include_answer": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        lines = []
        for i, r in enumerate(results[:num_results]):
            lines.append(f"{i+1}. {r.get('title', 'N/A')}: {r.get('url', 'N/A')}")

        output = f"Search results for '{query}':\n" + "\n".join(lines)
        if data.get("answer"):
            output += f"\n\nAnswer: {data['answer']}"

        return ToolResult(
            tool="tavily_search",
            input={"query": query, "num_results": num_results},
            output=output,
            success=True,
            latency_ms=int((time.time() - start) * 1000),
        )
    except Exception as exc:
        return ToolResult(
            tool="tavily_search",
            input={"query": query, "num_results": num_results},
            output="",
            success=False,
            latency_ms=int((time.time() - start) * 1000),
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Placeholder Coding Tool (stub — file access + execution for future)
# ---------------------------------------------------------------------------

async def _coding_impl(command: str, **kwargs) -> ToolResult:
    """Placeholder coding tool stub. Full implementation: file reads/writes, diffs."""
    return ToolResult(
        tool="coding",
        input={"command": command, **kwargs},
        output=(
            "Coding tool is stubbed for MVP. "
            "Full implementation: file reads/writes, diff view, terminal execution."
        ),
        success=True,
        latency_ms=0,
    )


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """
    Central registry for agent tools.
    Exposes tools to the ReAct loop via OpenAI tool_calls format.
    """

    def __init__(self):
        self._tools: dict[str, ToolDef] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register the MVP tool set."""
        self.register(
            ToolDef(
                name="web_search",
                description=(
                    "Search the web for current information, news, or facts. "
                    "Use this when you need up-to-date information that you cannot infer from memory alone."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to look up on the web.",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to return (default 5).",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
                handler=_web_search_impl,
            )
        )
        # Register Tavily as a secondary search if key is available
        self.register(
            ToolDef(
                name="tavily_search",
                description=(
                    "Search the web via Tavily API with AI-generated answer summary. "
                    "Requires TAVILY_API_KEY env var. Use when you need more accurate, "
                    "LLM-enhanced search results."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query."},
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results (default 5).",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
                handler=_tavily_search_impl,
            )
        )
        self.register(
            ToolDef(
                name="coding",
                description=(
                    "Execute coding tasks: read files, write files, run shell commands, "
                    "show git diffs. Stubbed for MVP — full implementation planned post-hackathon."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The coding command: 'read', 'write', 'exec', 'diff'.",
                        },
                        "path": {"type": "string", "description": "File path (for read/write)."},
                        "content": {"type": "string", "description": "File content (for write)."},
                    },
                    "required": ["command"],
                },
                handler=_coding_impl,
            )
        )

    def register(self, tool: ToolDef) -> None:
        """Register a new tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    @property
    def tools(self) -> dict[str, ToolDef]:
        return dict(self._tools)

    def openai_schema(self) -> list[dict]:
        """Return the tool definitions in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self._tools.values()
        ]

    async def execute(self, tool_name: str, tool_input: dict) -> ToolResult:
        """Execute a tool by name with the given input dict."""
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                tool=tool_name,
                input=tool_input,
                output="",
                success=False,
                error=f"Unknown tool: {tool_name}",
            )
        try:
            result = await tool.handler(**tool_input)
            return result
        except Exception as exc:
            return ToolResult(
                tool=tool_name,
                input=tool_input,
                output="",
                success=False,
                error=f"Tool execution failed: {exc}",
            )
