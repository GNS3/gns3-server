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
from langgraph.checkpoint.sqlite import SqliteSaver
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
        self.config = config
        self.controller = controller
        self._agent = None
        self._checkpointer = None
        self._tools = []
        self._tools_by_name = {}
        self._model_with_tools = None

    def _create_model(self):
        """
        Create a fresh LLM model instance from configuration.
        """
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
            log.info(f"Model created: {self.config.provider}/{self.config.model_name}")
            return model
        except Exception as e:
            log.error(f"Failed to create model: {e}")
            raise RuntimeError(f"Failed to create model: {e}")

    def _get_tools(self):
        """
        Get available tools for the agent.
        """
        if not self._tools:
            # Import tools here to avoid circular dependencies
            from gns3server.services.copilot_tools import (
                GNS3TopologyTool,
                GNS3CreateNodeTool,
                GNS3StartNodeTool,
                GNS3LinkTool,
                GNS3TemplateTool,
                ExecuteDisplayCommandsTool,
                ExecuteConfigCommandsTool,
                VPCSCommandsTool,
            )

            # Create tool instances with controller
            self._tools = [
                GNS3TemplateTool(controller=self.controller),
                GNS3TopologyTool(controller=self.controller),
                GNS3CreateNodeTool(controller=self.controller),
                GNS3StartNodeTool(controller=self.controller),
                GNS3LinkTool(controller=self.controller),
                ExecuteDisplayCommandsTool(controller=self.controller),
                ExecuteConfigCommandsTool(controller=self.controller),
                VPCSCommandsTool(controller=self.controller),
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
            model = self._create_model()
            tools = self._get_tools()
            self._model_with_tools = model.bind_tools(tools)
            log.info(f"Model bound with {len(tools)} tools")
        return self._model_with_tools

    def __init__(self, config: schemas.CopilotConfig, controller: Controller):
        """
        Initialize the copilot service.

        :param config: Copilot configuration
        :param controller: GNS3 controller instance
        """
        self.config = config
        self.controller = controller
        self._agents = {}  # Cache agents by project_id
        self._tools = []
        self._tools_by_name = {}
        self._model_with_tools = None

    def _get_checkpointer(self, project_id: str):
        """
        Get or create a SQLite checkpointer for a specific project.

        :param project_id: GNS3 project ID
        :return: SqliteSaver instance
        """
        # Import here to avoid circular dependency
        from gns3server.controller.project import Project

        # Get the project to find its directory
        project = self.controller.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Create checkpoint file in the project directory
        checkpointer_path = os.path.join(project.path, "copilot_checkpoints.db")

        # Store the path for reference
        self._project_checkpoint_path = checkpointer_path

        # Check if we already created a checkpointer for this project
        if self._checkpointer and self._project_checkpoint_path == checkpointer_path:
            return self._checkpointer

        # Create new checkpointer
        import sqlite3
        conn = sqlite3.connect(checkpointer_path, check_same_thread=False)
        self._checkpointer = SqliteSaver(conn)
        log.info(f"Project checkpointer created at {checkpointer_path}")

        return self._checkpointer

    def _build_agent(self, project_id: str):
        """
        Build and compile the LangGraph agent with tools for a specific project.

        :param project_id: GNS3 project ID
        :return: Compiled LangGraph agent
        """
        # Get project-specific checkpointer
        checkpointer = self._get_checkpointer(project_id)

        # Define state
        class AgentState(MessagesState):
            pass

        # Define LLM call node
        def llm_call(state: dict):
            """LLM decides whether to call a tool or not"""
            system_prompt = self._get_system_prompt()

            # Build messages with system prompt
            context_messages = [SystemMessage(content=system_prompt)]

            # Combine with existing messages
            full_messages = context_messages + state["messages"]

            # Get model with tools
            model_with_tools = self._get_model_with_tools()

            response = model_with_tools.invoke(full_messages)
            return {
                "messages": [response],
                "llm_calls": state.get("llm_calls", 0) + 1,
            }

        # Define tool execution node
        def tool_node(state: dict):
            """Execute tool calls"""
            results = []
            for tool_call in state["messages"][-1].tool_calls:
                tool = self._tools_by_name[tool_call["name"]]
                try:
                    # Parse tool arguments
                    if isinstance(tool_call.get("args"), dict):
                        tool_input = json.dumps(tool_call["args"])
                    else:
                        tool_input = str(tool_call.get("args", {}))

                    # Execute tool
                    observation = tool._run(tool_input)

                    results.append(
                        ToolMessage(
                            content=observation,
                            tool_call_id=tool_call["id"],
                            name=tool_call["name"]
                        )
                    )
                except Exception as e:
                    log.error(f"Tool {tool_call['name']} failed: {e}")
                    results.append(
                        ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_call["id"],
                            name=tool_call["name"]
                        )
                    )
            return {"messages": results}

        # Define routing logic
        def should_continue(state: MessagesState) -> Literal["tool_node", END]:
            """Determine the next step after LLM response"""
            last_message = state["messages"][-1]

            # LLM requested tool calls
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tool_node"

            return END

        # Build workflow
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
        return agent

    def _get_agent(self, project_id: str):
        """
        Get or create the copilot agent instance for a specific project.

        :param project_id: GNS3 project ID
        :return: Compiled LangGraph agent
        """
        if project_id not in self._agents:
            self._agents[project_id] = self._build_agent(project_id)
            log.info(f"Created new agent for project {project_id}")
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
        Get a textual representation of the project topology.

        :param project: GNS3 project
        :return: Topology description
        """
        try:
            lines = [f"Project: {project.name} ({project.id})"]
            lines.append(f"Nodes: {len(project.nodes)}")

            for node in project.nodes:
                lines.append(f"  - {node.name} ({node.node_type})")

            lines.append(f"Links: {len(project.links)}")

            for link in project.links:
                lines.append(f"  - {link.node_a.name} <-> {link.node_b.name}")

            return "\n".join(lines)

        except Exception as e:
            log.error(f"Error getting topology context: {e}")
            return f"Project: {project.name} (unable to load topology details)"

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
        # Get project-specific agent
        agent = self._get_agent(project_id)

        try:
            # Get project topology context
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

            return {
                "response": response,
                "tools_used": tools_used,
            }

        except Exception as e:
            log.error(f"Error in copilot chat: {str(e)}")
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
        # Get project-specific agent
        agent = self._get_agent(project_id)

        try:
            # Get project topology context
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
            config = {"configurable": {"thread_id": conversation_id}}

            async for chunk in agent.astream({"messages": messages}, config=config):
                # Process the chunk and yield events
                if "messages" in chunk:
                    for msg in chunk["messages"]:
                        if isinstance(msg, AIMessage):
                            # Stream text content
                            if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content:
                                yield schemas.ChatStreamEvent(
                                    event="token",
                                    data=msg.content,
                                    conversation_id=conversation_id
                                )
                            # Stream tool calls
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    tool_name = tool_call.get("name", "unknown")
                                    yield schemas.ChatStreamEvent(
                                        event="tool_call",
                                        data=tool_name,
                                        conversation_id=conversation_id
                                    )
                        elif isinstance(msg, ToolMessage):
                            # Tool execution result
                            yield schemas.ChatStreamEvent(
                                event="tool_result",
                                data=f"{msg.name}: {msg.content[:100]}...",
                                conversation_id=conversation_id
                            )

            # Send done event
            yield schemas.ChatStreamEvent(
                event="done",
                data="",
                conversation_id=conversation_id
            )

        except Exception as e:
            log.error(f"Error in copilot chat stream: {str(e)}")
            yield schemas.ChatStreamEvent(
                event="error",
                data=str(e),
                conversation_id=conversation_id
            )
