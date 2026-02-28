#!/usr/bin/env python
#
# Copyright (C) 2025 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Service for interacting with the GNS3 Copilot agent.

This service uses LangChain and LangGraph to provide AI-powered assistance
for GNS3 network automation tasks.
"""

import json
import logging
import os
from typing import AsyncGenerator, Literal

from langchain.chat_models import init_chat_model
from langchain.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.managed.is_last_step import RemainingSteps
from typing_extensions import TypedDict

from gns3server.controller import Controller
from gns3server.schemas.controller.copilot import ChatStreamEvent, CopilotConfig, OpenAIToolCall

log = logging.getLogger(__name__)


class MessagesState(TypedDict):
    """
    GNS3 Copilot conversation state management class.
    """

    messages: list[AnyMessage]
    llm_calls: int
    remaining_steps: RemainingSteps


class CopilotService:
    """
    Service for interacting with the GNS3 Copilot agent.
    """

    def __init__(self, config: CopilotConfig, controller: Controller):
        """
        Initialize the copilot service.

        :param config: Copilot configuration
        :param controller: GNS3 controller instance
        """
        log.info("Initializing CopilotService with config: %s/%s", config.provider, config.model_name)
        self.config = config
        self.controller = controller
        self._agents = {}  # Cache agents by project_id
        self._tools = []
        self._tools_by_name = {}
        self._model_with_tools = None
        self._checkpointer = None
        self._checkpointer_conn = None  # Save connection reference to prevent GC
        self._project_checkpoint_path = None
        log.debug("CopilotService initialized successfully")

    def _create_model(self):
        """
        Create a fresh LLM model instance from configuration.
        """
        log.debug("Creating model: %s/%s", self.config.provider, self.config.model_name)
        model_kwargs = {
            "temperature": str(self.config.temperature),
            "configurable_fields": "any",
            "config_prefix": "copilot",
        }

        if self.config.api_key:
            model_kwargs["api_key"] = self.config.api_key

        if self.config.base_url:
            model_kwargs["base_url"] = self.config.base_url

        if self.config.max_tokens:
            model_kwargs["max_tokens"] = self.config.max_tokens

        try:
            model = init_chat_model(
                self.config.model_name,
                model_provider=self.config.provider,
                **model_kwargs
            )
            log.info("Model created successfully: %s/%s", self.config.provider, self.config.model_name)
            return model
        except Exception as e:
            log.error("Failed to create model: %s", e, exc_info=True)
            raise RuntimeError(f"Failed to create model: {e}")

    def _get_tools(self):
        """
        Get available tools for the agent.
        """
        if not self._tools:
            log.debug("Loading copilot tools...")
            # Import tools here to avoid circular dependencies
            from gns3server.services.copilot_tools import (
                GNS3TopologyTool,
                GNS3CreateNodeTool,
                GNS3StartNodeTool,
                GNS3LinkTool,
                GNS3TemplateTool,
                ReadDeviceInfoTool,
                ApplyDeviceConfigTool,
                VPCSTerminalTool,
            )

            # Create tool instances with controller
            self._tools = [
                GNS3TemplateTool(controller=self.controller),
                GNS3TopologyTool(controller=self.controller),
                GNS3CreateNodeTool(controller=self.controller),
                GNS3StartNodeTool(controller=self.controller),
                GNS3LinkTool(controller=self.controller),
                ReadDeviceInfoTool(controller=self.controller),
                ApplyDeviceConfigTool(controller=self.controller),
                VPCSTerminalTool(controller=self.controller),
            ]

            # Build tools by name dict
            self._tools_by_name = {tool.name: tool for tool in self._tools}
            log.info("Loaded %d tools: %s", len(self._tools), [t.name for t in self._tools])

        return self._tools

    def _get_model_with_tools(self):
        """
        Get model with tools bound.
        """
        if self._model_with_tools is None:
            log.debug("Binding tools to model...")
            model = self._create_model()
            tools = self._get_tools()
            self._model_with_tools = model.bind_tools(tools)
            log.info("Model bound with %d tools", len(tools))
        return self._model_with_tools

    async def _get_checkpointer(self, project_id: str):
        """
        Get or create a SQLite checkpointer for a specific project.

        :param project_id: GNS3 project ID
        :return: AsyncSqliteSaver instance
        """
        log.debug("Getting checkpointer for project %s", project_id)

        # Get the project to find its directory
        project = self.controller.get_project(project_id)
        if not project:
            log.error("Project %s not found in controller", project_id)
            raise ValueError(f"Project {project_id} not found")

        # Create checkpoint file in the project directory
        checkpointer_path = os.path.join(project.path, "copilot_checkpoints.db")
        log.debug("Checkpoint path: %s", checkpointer_path)

        # Store the path for reference
        self._project_checkpoint_path = checkpointer_path

        # Check if we already created a checkpointer for this project
        if self._checkpointer and self._project_checkpoint_path == checkpointer_path:
            log.debug("Reusing existing checkpointer")
            return self._checkpointer

        # Create new checkpointer using AsyncSqliteSaver
        log.debug("Creating new async checkpointer at %s", checkpointer_path)
        import aiosqlite

        # Close existing connection if switching projects
        if self._checkpointer_conn:
            try:
                await self._checkpointer_conn.close()
                log.debug("Closed previous checkpointer connection")
            except Exception as e:
                log.warning("Error closing old checkpointer connection: %s", e)

        # Create new connection
        conn = await aiosqlite.connect(checkpointer_path)
        # Enable WAL mode for better concurrent performance
        await conn.execute("PRAGMA journal_mode=WAL;")
        self._checkpointer_conn = conn  # Save connection reference to prevent GC
        self._checkpointer = AsyncSqliteSaver(conn)

        # CRITICAL: Initialize database schema
        await self._checkpointer.setup()

        log.info("Project async checkpointer created and initialized at %s", checkpointer_path)

        return self._checkpointer

    async def _build_agent(self, project_id: str):
        """
        Build and compile the LangGraph agent with tools for a specific project.

        :param project_id: GNS3 project ID
        :return: Compiled LangGraph agent
        """
        log.info("Building agent for project %s", project_id)

        # Get project-specific checkpointer
        checkpointer = await self._get_checkpointer(project_id)

        # Define state
        class AgentState(MessagesState):
            pass

        # Define LLM call node
        def llm_call(state: dict):
            """LLM decides whether to call a tool or not"""
            log.debug("Executing LLM call node")

            # Get system prompt
            system_prompt = self._get_system_prompt()

            # Build messages with system prompt and context
            # Following FlowNet-Lab's approach: always prepend system prompt
            context_messages = []
            project_context = state.get("project_context")
            if project_context:
                context_messages.append(SystemMessage(content=project_context))
                log.debug("Added project context to messages (length: %d chars)", len(project_context))

            # Combine: system prompt + context + conversation history
            full_messages = [SystemMessage(content=system_prompt)] + context_messages + state["messages"]

            # Log message structure for debugging
            log.debug("LLM call message structure:")
            log.debug("  System prompt length: %d chars", len(system_prompt))
            log.debug("  Context messages: %d", len(context_messages))
            log.debug("  Conversation history: %d messages", len(state["messages"]))
            log.debug("  Total messages: %d", len(full_messages))

            # Get model with tools
            model_with_tools = self._get_model_with_tools()

            response = model_with_tools.invoke(full_messages)
            tool_calls_count = len(response.tool_calls) if hasattr(response, 'tool_calls') else 0
            log.debug("LLM response received, tool_calls: %d", tool_calls_count)
            return {
                "messages": [response],
                "llm_calls": state.get("llm_calls", 0) + 1,
            }

        # Define tool execution node (async)
        async def tool_node(state: dict):
            """Execute tool calls"""
            tool_calls = state["messages"][-1].tool_calls
            log.debug("Executing %d tool calls", len(tool_calls))
            results = []
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                log.info("Executing tool: %s", tool_name)
                tool = self._tools_by_name[tool_name]
                try:
                    # Parse tool arguments
                    if isinstance(tool_call.get("args"), dict):
                        tool_input = json.dumps(tool_call["args"])
                    else:
                        tool_input = str(tool_call.get("args", {}))

                    log.debug("Tool %s input: %s...", tool_name, tool_input[:200])

                    # Execute tool (use _arun for async tools)
                    if hasattr(tool, '_arun'):
                        observation = await tool._arun(tool_input)
                    else:
                        observation = tool._run(tool_input)

                    log.debug("Tool %s result: %s...", tool_name, observation[:200])
                    results.append(
                        ToolMessage(
                            content=observation,
                            tool_call_id=tool_call["id"],
                            name=tool_name
                        )
                    )
                except Exception as e:
                    log.error("Tool %s failed: %s", tool_name, e, exc_info=True)
                    results.append(
                        ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_call["id"],
                            name=tool_name
                        )
                    )
            return {"messages": results}

        # Define routing logic
        def should_continue(state: MessagesState) -> Literal["tool_node", END]:
            """Determine the next step after LLM response"""
            last_message = state["messages"][-1]

            # LLM requested tool calls
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                log.debug("Routing to tool_node, %d tools to execute", len(last_message.tool_calls))
                return "tool_node"

            log.debug("Routing to END (no more tool calls)")
            return END

        # Build workflow
        log.debug("Building agent workflow graph")
        agent_builder = StateGraph(AgentState)
        agent_builder.add_node("llm_call", llm_call)
        agent_builder.add_node("tool_node", tool_node)
        agent_builder.add_edge(START, "llm_call")
        agent_builder.add_conditional_edges(
            "llm_call",
            should_continue,
            {
                "tool_node": "tool_node",
                END: END,
            },
        )
        agent_builder.add_edge("tool_node", "llm_call")

        # Compile with project-specific checkpointer
        agent = agent_builder.compile(checkpointer=checkpointer)
        log.info("Agent built successfully for project %s", project_id)
        return agent

    async def _get_agent(self, project_id: str):
        """
        Get or create the copilot agent instance for a specific project.

        :param project_id: GNS3 project ID
        :return: Compiled LangGraph agent
        """
        if project_id not in self._agents:
            log.info("No cached agent for project %s, creating new one", project_id)
            self._agents[project_id] = await self._build_agent(project_id)
        else:
            log.debug("Using cached agent for project %s", project_id)
        return self._agents[project_id]

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the agent.
        """
        # Use gns3-copilot's base prompt
        from gns3server.services.copilot_prompts import SYSTEM_PROMPT
        return SYSTEM_PROMPT

    def _get_topology_context_from_state(self, state: dict) -> str:
        """
        Get topology context from state if available.
        """
        # For now, return None. In the future, we can inject topology info here
        return None

    async def chat(
        self,
        message: str,
        project_id: str,
        conversation_id: str,
    ) -> dict:
        """
        Send a message to the copilot agent and get a response.

        :param message: User message
        :param project_id: GNS3 project ID
        :param conversation_id: Conversation/thread ID
        :return: Response dictionary with 'response' and optionally 'tools_used'
        """
        log.info("Chat request - project: %s, conversation: %s, message: %s...",
                 project_id, conversation_id, message[:100])

        # Get project-specific agent
        agent = await self._get_agent(project_id)

        try:
            # Get topology using the topology tool
            log.debug("Getting topology for project %s using topology tool", project_id)
            from gns3server.services.copilot_tools.topology import GNS3TopologyTool

            topology_tool = GNS3TopologyTool(controller=self.controller)
            topology_input = json.dumps({"project_id": project_id})
            topology_result = await topology_tool._arun(topology_input)

            # Get the base system prompt from gns3-copilot
            base_prompt = self._get_system_prompt()

            # Prepare system message with project context and topology
            system_message = f"""{base_prompt}

### CURRENT PROJECT CONTEXT ###
You are working on GNS3 project: {project_id}

Current project topology:
{topology_result}

**CRITICAL:** When calling tools, ALWAYS use project_id: "{project_id}"
"""

            # Log the system prompt for debugging
            log.info("=== AGENT SYSTEM PROMPT ===")
            log.info("Project ID: %s", project_id)
            log.info("Conversation ID: %s", conversation_id)
            log.info("Base prompt length: %d chars", len(base_prompt))
            log.info("Topology result length: %d chars", len(topology_result))
            log.info("Total system prompt length: %d chars", len(system_message))
            log.info("Topology data:\n%s", topology_result)
            log.info("=== END SYSTEM PROMPT ===")

            # Prepare the input message
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=message),
            ]

            # Invoke the agent
            log.debug("Invoking agent with thread_id: %s", conversation_id)
            config = {"configurable": {"thread_id": conversation_id}}
            result = await agent.ainvoke({"messages": messages}, config=config)

            # Extract the response
            response_messages = result.get("messages", [])
            response = ""
            tools_used = []

            for msg in response_messages:
                if hasattr(msg, "content"):
                    if isinstance(msg.content, str):
                        response += msg.content
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tools_used.append(tool_call.get("name", "unknown"))

            log.info("Chat response - tools_used: %s, response_length: %d",
                     tools_used, len(response))
            return {
                "response": response,
                "tools_used": tools_used,
            }

        except Exception as e:
            log.error("Error in copilot chat: %s", str(e), exc_info=True)
            raise

    async def chat_stream(
        self,
        message: str,
        project_id: str,
        conversation_id: str,
    ) -> AsyncGenerator[ChatStreamEvent, None]:
        """
        Stream a chat response from the copilot agent with token-level granularity.

        Uses LangGraph's astream_events() API to get fine-grained events including:
        - Token-level content streaming
        - Tool call start/end events
        - Progressive tool call arguments

        :param message: User message
        :param project_id: GNS3 project ID
        :param conversation_id: Conversation/thread ID
        :yields: ChatStreamEvent objects
        """
        log.info("Chat stream request - project: %s, conversation: %s, message: %s...",
                 project_id, conversation_id, message[:100])

        # Get project-specific agent
        agent = await self._get_agent(project_id)

        try:
            # Prepare messages with topology context (returns messages + context string)
            messages, context_message = await self._prepare_stream_messages(project_id, message)

            # Log conversation info
            log.info("Conversation ID: %s", conversation_id)

            # Prepare input for the agent
            inputs = {
                "messages": messages,
                "llm_calls": 0,
                "remaining_steps": 20,
                "project_context": context_message,  # Pass context to llm_call node
            }
            config = {"configurable": {"thread_id": conversation_id}}

            # Import stream utilities
            from gns3server.services.copilot_utils import ToolCallStreamAccumulator, convert_stream_event_to_sse

            # Initialize tool call accumulator for stateful tool call handling
            tool_call_accumulator = ToolCallStreamAccumulator()

            log.debug("Starting agent stream_events with thread_id: %s", conversation_id)

            # Use astream_events for token-level streaming
            event_stream = agent.astream_events(
                inputs,
                config=config,
                version="v2",  # Use v2 for more detailed events
            )

            async for event in event_stream:
                event_type = event.get("event", "")

                # Use accumulator for tool_call events (stateful)
                if event_type == "on_chat_model_stream":
                    chunks = tool_call_accumulator.process_event(event)
                    for chunk in chunks:
                        if chunk.get("type") == "content":
                            yield ChatStreamEvent(
                                type="content",
                                content=chunk.get("content", ""),
                                message_id=chunk.get("message_id"),
                                conversation_id=conversation_id
                            )
                        elif chunk.get("type") == "tool_call":
                            tool_call_data = chunk.get("tool_call", {})
                            function_data = tool_call_data.get("function", {})
                            yield ChatStreamEvent(
                                type="tool_call",
                                tool_call=OpenAIToolCall(
                                    id=tool_call_data.get("id", ""),
                                    type=tool_call_data.get("type", "function"),
                                    function={
                                        "name": function_data.get("name", ""),
                                        "arguments": function_data.get("arguments", ""),
                                        "complete": function_data.get("complete", False)
                                    }
                                ),
                                conversation_id=conversation_id
                            )

                # Use stateless converter for other events
                elif event_type in ("on_tool_start", "on_tool_end"):
                    sse_event = convert_stream_event_to_sse(event)
                    if sse_event.get("type") == "tool_start":
                        yield ChatStreamEvent(
                            type="tool_start",
                            tool_name=sse_event.get("tool_name", ""),
                            conversation_id=conversation_id
                        )
                    elif sse_event.get("type") == "tool_end":
                        yield ChatStreamEvent(
                            type="tool_end",
                            tool_name=sse_event.get("tool_name", ""),
                            tool_output=sse_event.get("tool_output", ""),
                            conversation_id=conversation_id
                        )

            # Send done event
            log.info("Chat stream completed for conversation %s", conversation_id)
            yield ChatStreamEvent(
                type="done",
                conversation_id=conversation_id
            )

        except Exception as e:
            log.error("Error in copilot chat stream: %s", str(e), exc_info=True)
            yield ChatStreamEvent(
                type="error",
                error=str(e),
                conversation_id=conversation_id
            )

    async def _prepare_stream_messages(self, project_id: str, message: str) -> tuple:
        """
        Prepare messages with topology context for streaming.

        :param project_id: GNS3 project ID
        :param message: User message
        :return: Tuple of (messages list, topology info string)
        """
        # Get topology using the topology tool
        log.debug("Getting topology for project %s using topology tool", project_id)
        from gns3server.services.copilot_tools.topology import GNS3TopologyTool

        topology_tool = GNS3TopologyTool(controller=self.controller)
        topology_input = json.dumps({"project_id": project_id})
        topology_result = await topology_tool._arun(topology_input)

        # Get the base system prompt from gns3-copilot
        base_prompt = self._get_system_prompt()

        # Prepare context message with project context and topology
        # This will be combined with system prompt in llm_call node
        context_message = """### CURRENT PROJECT CONTEXT ###
You are working on GNS3 project: %s

Current project topology:
%s

**CRITICAL:** When calling tools, ALWAYS use project_id: "%s"
""" % (project_id, topology_result, project_id)

        # Log the system prompt for debugging
        log.info("=== AGENT SYSTEM PROMPT ===")
        log.info("Project ID: %s", project_id)
        log.info("Base prompt length: %d chars", len(base_prompt))
        log.info("Topology result length: %d chars", len(topology_result))
        log.info("Context message length: %d chars", len(context_message))
        log.info("Topology data:\n%s", topology_result)
        log.info("=== END SYSTEM PROMPT ===")

        # Only return human message - system prompt will be added by llm_call node
        # This matches FlowNet-Lab's approach
        return [HumanMessage(content=message)], context_message

    async def close(self):
        """
        Close the copilot service and cleanup database connections.

        This should be called when shutting down the service to properly
        close the SQLite checkpointer connection.
        """
        log.info("Closing CopilotService")
        if self._checkpointer_conn:
            await self._checkpointer_conn.close()
            self._checkpointer_conn = None
            self._checkpointer = None
            log.info("Copilot checkpointer connection closed")
        self._agents.clear()
        log.info("CopilotService closed")
