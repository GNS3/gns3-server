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
import aiosqlite
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
    # Store project_id for multi-turn conversations
    # This ensures the correct project_id is available across tool calls
    project_id: str | None
    # Store topology information to avoid repeated fetches
    # Following FlowNet-Lab's approach
    topology_info: dict | None


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
            # Get system prompt
            system_prompt = self._get_system_prompt()

            # Get project_id from state (persisted across turns)
            project_id = state.get("project_id")

            # Build context messages - fetch topology on EVERY llm_call
            # This ensures AI always sees the latest topology
            context_messages = []
            topology_info = None

            if project_id:
                try:
                    from gns3server.services.copilot_tools.topology import GNS3TopologyTool

                    topology_tool = GNS3TopologyTool(controller=self.controller)
                    topology = topology_tool._run(project_id=project_id)

                    if topology and "error" not in topology:
                        topology_info = topology
                        log.info("Retrieved topology for project %s: %d nodes, %d links",
                                 project_id, topology.get("nodes_count", 0), topology.get("links_count", 0))

                        context_messages.append(
                            SystemMessage(
                                content=f"Current Context: Project_ID={project_id}\n\nTopology:\n{topology}"
                            )
                        )
                    else:
                        log.warning("Failed to retrieve topology: %s", topology.get("error", "Unknown"))
                        context_messages.append(
                            SystemMessage(content=f"Current Context: Project_ID={project_id}")
                        )
                except Exception as e:
                    log.warning("Error retrieving topology: %s", e)
                    context_messages.append(
                        SystemMessage(content=f"Current Context: Project_ID={project_id}")
                    )

            # Merge message lists
            full_messages = [SystemMessage(content=system_prompt)] + context_messages + state["messages"]

            # Create fresh model with tools
            model_with_tools = self._get_model_with_tools()
            response = model_with_tools.invoke(full_messages)

            return {
                "messages": [response],
                "llm_calls": state.get("llm_calls", 0) + 1,
                "topology_info": topology_info,
            }

        # Define tool execution node
        def tool_node(state: dict):
            """
            Execute tool calls.

            Simple implementation using tool.invoke() - LangChain handles
            the internal logic of calling _run or _arun automatically.
            """
            last_message = state["messages"][-1]
            tool_calls = last_message.tool_calls

            log.info("Executing %d tool calls", len(tool_calls))
            log.info("tool_calls %s", tool_calls)

            results = []
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_call_id = tool_call["id"]

                log.info("Executing tool: %s", tool_name)
                log.info("tool_call args: %s", tool_call["args"])
                tool = self._tools_by_name[tool_name]
                try:
                    # Use tool.invoke() - LangChain handles the rest
                    # Pass tool_call["args"] directly (can be dict or JSON string)
                    observation = tool.invoke(tool_call["args"])

                    # Ensure result is string
                    if not isinstance(observation, str):
                        observation = json.dumps(observation, ensure_ascii=False)

                    log.debug("Tool %s result: %s...", tool_name, observation[:200] if observation else "empty")
                    results.append(
                        ToolMessage(
                            content=observation,
                            tool_call_id=tool_call_id,
                            name=tool_name
                        )
                    )
                except Exception as e:
                    log.error("Tool %s failed: %s", tool_name, e, exc_info=True)
                    results.append(
                        ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_call_id,
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
            # Log conversation info
            log.info("Conversation ID: %s", conversation_id)

            # Prepare the input message (topology will be fetched in llm_call node)
            # Following FlowNet-Lab's approach: only human message, system prompt added in llm_call
            messages = [HumanMessage(content=message)]

            # Invoke the agent with project_id in state
            log.debug("Invoking agent with thread_id: %s", conversation_id)
            config = {"configurable": {"thread_id": conversation_id}}
            inputs = {
                "messages": messages,
                "llm_calls": 0,
                "remaining_steps": 20,
                "project_id": project_id,  # Store in state for multi-turn conversations
                "topology_info": None,  # Will be fetched on first llm_call
            }
            result = await agent.ainvoke(inputs, config=config)

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
            # Prepare messages (topology will be fetched in llm_call node)
            messages = [HumanMessage(content=message)]

            # Log conversation info
            log.info("Conversation ID: %s", conversation_id)

            # Prepare input for the agent
            inputs = {
                "messages": messages,
                "llm_calls": 0,
                "remaining_steps": 20,
                "project_id": project_id,  # Store in state for multi-turn conversations
                "topology_info": None,  # Will be fetched on first llm_call
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
