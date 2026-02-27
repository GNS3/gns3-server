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
import os
import sqlite3
from typing import Any, AsyncGenerator, Literal, Optional
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain.messages import (
    AnyMessage,
    SystemMessage,
    ToolMessage,
    HumanMessage,
    AIMessage,
)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.managed.is_last_step import RemainingSteps
from typing_extensions import TypedDict

from gns3server import schemas
from gns3server.controller import Controller

import logging

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

    def __init__(self, config: schemas.CopilotConfig, controller: Controller):
        """
        Initialize the copilot service.

        :param config: Copilot configuration
        :param controller: GNS3 controller instance
        """
        log.info(f"Initializing CopilotService with config: {config.provider}/{config.model_name}")
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
        log.debug(f"Creating model: {self.config.provider}/{self.config.model_name}")
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
            log.info(f"Model created successfully: {self.config.provider}/{self.config.model_name}")
            return model
        except Exception as e:
            log.error(f"Failed to create model: {e}", exc_info=True)
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
            log.info(f"Loaded {len(self._tools)} tools: {[t.name for t in self._tools]}")

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
            log.info(f"Model bound with {len(tools)} tools")
        return self._model_with_tools

    async def _get_checkpointer(self, project_id: str):
        """
        Get or create a SQLite checkpointer for a specific project.

        :param project_id: GNS3 project ID
        :return: AsyncSqliteSaver instance
        """
        log.debug(f"Getting checkpointer for project {project_id}")

        # Import here to avoid circular dependency
        from gns3server.controller.project import Project

        # Get the project to find its directory
        project = self.controller.get_project(project_id)
        if not project:
            log.error(f"Project {project_id} not found in controller")
            raise ValueError(f"Project {project_id} not found")

        # Create checkpoint file in the project directory
        checkpointer_path = os.path.join(project.path, "copilot_checkpoints.db")
        log.debug(f"Checkpoint path: {checkpointer_path}")

        # Store the path for reference
        self._project_checkpoint_path = checkpointer_path

        # Check if we already created a checkpointer for this project
        if self._checkpointer and self._project_checkpoint_path == checkpointer_path:
            log.debug("Reusing existing checkpointer")
            return self._checkpointer

        # Create new checkpointer using AsyncSqliteSaver
        log.debug(f"Creating new async checkpointer at {checkpointer_path}")
        import aiosqlite

        # Close existing connection if switching projects
        if self._checkpointer_conn:
            try:
                await self._checkpointer_conn.close()
                log.debug("Closed previous checkpointer connection")
            except Exception as e:
                log.warning(f"Error closing old checkpointer connection: {e}")

        # Create new connection
        conn = await aiosqlite.connect(checkpointer_path)
        # Enable WAL mode for better concurrent performance
        await conn.execute("PRAGMA journal_mode=WAL;")
        self._checkpointer_conn = conn  # Save connection reference to prevent GC
        self._checkpointer = AsyncSqliteSaver(conn)

        # CRITICAL: Initialize database schema
        await self._checkpointer.setup()

        log.info(f"Project async checkpointer created and initialized at {checkpointer_path}")

        return self._checkpointer

    async def _build_agent(self, project_id: str):
        """
        Build and compile the LangGraph agent with tools for a specific project.

        :param project_id: GNS3 project ID
        :return: Compiled LangGraph agent
        """
        log.info(f"Building agent for project {project_id}")

        # Get project-specific checkpointer
        checkpointer = await self._get_checkpointer(project_id)

        # Define state
        class AgentState(MessagesState):
            pass

        # Define LLM call node
        def llm_call(state: dict):
            """LLM decides whether to call a tool or not"""
            log.debug("Executing LLM call node")
            system_prompt = self._get_system_prompt()

            # Build messages with system prompt
            context_messages = [SystemMessage(content=system_prompt)]

            # Combine with existing messages
            full_messages = context_messages + state["messages"]

            # Get model with tools
            model_with_tools = self._get_model_with_tools()

            response = model_with_tools.invoke(full_messages)
            log.debug(f"LLM response received, tool_calls: {len(response.tool_calls) if hasattr(response, 'tool_calls') else 0}")
            return {
                "messages": [response],
                "llm_calls": state.get("llm_calls", 0) + 1,
            }

        # Define tool execution node
        def tool_node(state: dict):
            """Execute tool calls"""
            tool_calls = state["messages"][-1].tool_calls
            log.debug(f"Executing {len(tool_calls)} tool calls")
            results = []
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                log.info(f"Executing tool: {tool_name}")
                tool = self._tools_by_name[tool_name]
                try:
                    # Parse tool arguments
                    if isinstance(tool_call.get("args"), dict):
                        tool_input = json.dumps(tool_call["args"])
                    else:
                        tool_input = str(tool_call.get("args", {}))

                    log.debug(f"Tool {tool_name} input: {tool_input[:200]}...")

                    # Execute tool
                    observation = tool._run(tool_input)

                    log.debug(f"Tool {tool_name} result: {observation[:200]}...")
                    results.append(
                        ToolMessage(
                            content=observation,
                            tool_call_id=tool_call["id"],
                            name=tool_name
                        )
                    )
                except Exception as e:
                    log.error(f"Tool {tool_name} failed: {e}", exc_info=True)
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
                log.debug(f"Routing to tool_node, {len(last_message.tool_calls)} tools to execute")
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
        log.info(f"Agent built successfully for project {project_id}")
        return agent

    async def _get_agent(self, project_id: str):
        """
        Get or create the copilot agent instance for a specific project.

        :param project_id: GNS3 project ID
        :return: Compiled LangGraph agent
        """
        if project_id not in self._agents:
            log.info(f"No cached agent for project {project_id}, creating new one")
            self._agents[project_id] = await self._build_agent(project_id)
        else:
            log.debug(f"Using cached agent for project {project_id}")
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

    def _get_topology_context(self, project) -> str:
        """
        Get a structured JSON representation of the project topology.

        Reference implementation from gns3-copilot's links_summary method.

        :param project: GNS3 project
        :return: JSON string with topology data
        """
        import json

        try:
            # Build nodes inventory (similar to gns3-copilot's nodes_inventory)
            nodes_data = {}
            for node_id, node in project.nodes.items():
                node_info = {
                    "name": node.name,
                    "node_id": node.id,
                    "node_type": node.node_type,
                    "status": node.status,
                    "x": node.x if hasattr(node, 'x') else 0,
                    "y": node.y if hasattr(node, 'y') else 0,
                }

                # Add ports if available (clean format like gns3-copilot)
                if hasattr(node, "ports") and node.ports:
                    node_info["ports"] = [
                        {"name": port.get("name"), "short_name": port.get("short_name")}
                        for port in node.ports
                    ]
                else:
                    node_info["ports"] = []

                nodes_data[node_id] = node_info

            # Build links summary (similar to gns3-copilot's links_summary)
            links_data = []
            for link in project.links.values():
                # Skip if link has no nodes
                if not link.nodes or len(link.nodes) < 2:
                    continue

                # Get both sides of the link
                side_a = link.nodes[0]
                side_b = link.nodes[1]

                # Get node objects
                node_a = project.nodes.get(side_a["node_id"])
                node_b = project.nodes.get(side_b["node_id"])

                if not node_a or not node_b:
                    continue

                # Get port names
                port_a_name = self._get_port_name(node_a, side_a.get("adapter_number"), side_a.get("port_number"))
                port_b_name = self._get_port_name(node_b, side_b.get("adapter_number"), side_b.get("port_number"))

                links_data.append({
                    "node_a": node_a.name,
                    "port_a": port_a_name,
                    "node_b": node_b.name,
                    "port_b": port_b_name,
                    "link_id": link.id if hasattr(link, 'id') else None
                })

            # Build structured topology (same format as gns3-copilot)
            topology = {
                "project_id": project.id,
                "name": project.name,
                "status": project.status if hasattr(project, 'status') else "opened",
                "nodes_count": len(nodes_data),
                "links_count": len(links_data),
                "nodes": nodes_data,
                "links": links_data
            }

            # Return as formatted JSON string
            topology_json = json.dumps(topology, indent=2, ensure_ascii=False)
            log.debug(f"Topology context: {topology_json[:200]}...")
            return topology_json

        except Exception as e:
            log.error(f"Error getting topology context: {e}", exc_info=True)
            # Return error info in JSON format
            error_json = json.dumps({
                "project_id": project.id,
                "name": project.name,
                "error": f"Unable to load topology details: {str(e)}"
            }, ensure_ascii=False)
            return error_json

    def _get_port_name(self, node, adapter_number: int, port_number: int) -> str:
        """
        Get port name from node by adapter and port number.

        :param node: GNS3 node object
        :param adapter_number: Adapter number
        :param port_number: Port number
        :return: Port name or placeholder
        """
        if not hasattr(node, "ports") or not node.ports:
            return f"adp{adapter_number}/prt{port_number}"

        for port in node.ports:
            if (port.get("adapter_number") == adapter_number and
                port.get("port_number") == port_number):
                return port.get("short_name", f"adp{adapter_number}/prt{port_number}")

        return f"adp{adapter_number}/prt{port_number}"

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
        log.info(f"Chat request - project: {project_id}, conversation: {conversation_id}, message: {message[:100]}...")

        # Get project-specific agent
        agent = await self._get_agent(project_id)

        try:
            # Get project topology context
            log.debug(f"Loading project {project_id} for topology context")
            project = await self.controller.get_loaded_project(project_id)
            topology_context = self._get_topology_context(project)

            # Get the base system prompt from gns3-copilot
            base_prompt = self._get_system_prompt()

            # Prepare system message with project context and tools
            # This is CRITICAL - LLM needs to know the project_id to call tools
            system_message = f"""{base_prompt}

### CURRENT PROJECT CONTEXT ###
You are working on GNS3 project: {project_id}

Current project topology:
{topology_context}

**CRITICAL:** When calling tools, ALWAYS use project_id: "{project_id}"
"""

            # Prepare the input message
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=message),
            ]

            # Invoke the agent
            log.debug(f"Invoking agent with thread_id: {conversation_id}")
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

            log.info(f"Chat response - tools_used: {tools_used}, response_length: {len(response)}")
            return {
                "response": response,
                "tools_used": tools_used,
            }

        except Exception as e:
            log.error(f"Error in copilot chat: {str(e)}", exc_info=True)
            raise

    async def chat_stream(
        self,
        message: str,
        project_id: str,
        conversation_id: str,
    ) -> AsyncGenerator[schemas.ChatStreamEvent, None]:
        """
        Stream a chat response from the copilot agent.

        :param message: User message
        :param project_id: GNS3 project ID
        :param conversation_id: Conversation/thread ID
        :yields: ChatStreamEvent objects
        """
        log.info(f"Chat stream request - project: {project_id}, conversation: {conversation_id}, message: {message[:100]}...")

        # Get project-specific agent
        agent = await self._get_agent(project_id)

        try:
            # Get project topology context
            log.debug(f"Loading project {project_id} for topology context")
            project = await self.controller.get_loaded_project(project_id)
            topology_context = self._get_topology_context(project)

            # Get the base system prompt from gns3-copilot
            base_prompt = self._get_system_prompt()

            # Prepare system message with project context and tools
            system_message = f"""{base_prompt}

### CURRENT PROJECT CONTEXT ###
You are working on GNS3 project: {project_id}

Current project topology:
{topology_context}

**CRITICAL:** When calling tools, ALWAYS use project_id: "{project_id}"
"""

            # Prepare the input message
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=message),
            ]

            # Stream the agent response
            log.debug(f"Starting agent stream with thread_id: {conversation_id}")
            config = {"configurable": {"thread_id": conversation_id}}

            async for chunk in agent.astream({"messages": messages}, config=config):
                # Process the chunk and yield events
                if "messages" in chunk:
                    for msg in chunk["messages"]:
                        if isinstance(msg, AIMessage):
                            # Stream text content
                            if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content:
                                log.debug(f"Streaming token: {msg.content[:50]}...")
                                yield schemas.ChatStreamEvent(
                                    event="token",
                                    data=msg.content,
                                    conversation_id=conversation_id
                                )
                            # Stream tool calls
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    tool_name = tool_call.get("name", "unknown")
                                    log.info(f"Streaming tool call: {tool_name}")
                                    yield schemas.ChatStreamEvent(
                                        event="tool_call",
                                        data=tool_name,
                                        conversation_id=conversation_id
                                    )
                        elif isinstance(msg, ToolMessage):
                            # Tool execution result
                            log.debug(f"Streaming tool result: {msg.name}")
                            yield schemas.ChatStreamEvent(
                                event="tool_result",
                                data=f"{msg.name}: {msg.content[:100]}...",
                                conversation_id=conversation_id
                            )

            # Send done event
            log.info(f"Chat stream completed for conversation {conversation_id}")
            yield schemas.ChatStreamEvent(
                event="done",
                data="",
                conversation_id=conversation_id
            )

        except Exception as e:
            log.error(f"Error in copilot chat stream: {str(e)}", exc_info=True)
            yield schemas.ChatStreamEvent(
                event="error",
                data=str(e),
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
