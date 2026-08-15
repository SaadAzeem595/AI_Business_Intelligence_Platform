from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import MockUser
from app.features.chat.schemas import ChatMessageResponse, ChatMessagePayload
from app.features.agents.schemas import AgentChatPayload
from app.features.agents.router import chat_with_agents


class ChatService:
    """Agentic assistant coordinating natural language requests to charts or structured tables."""

    @staticmethod
    async def get_assistant_response(
        payload: ChatMessagePayload,
        current_user: MockUser,
        db: AsyncSession
    ) -> ChatMessageResponse:
        active_proj = payload.active_project or payload.project_id
        session_id = getattr(payload, "sessionId", None)
        
        agent_payload = AgentChatPayload(
            message=payload.message,
            thread_id=payload.thread_id or session_id or payload.conversation_id,
            conversation_id=payload.conversation_id or payload.thread_id or session_id,
            workspace=payload.workspace or payload.workspace_id or "default",
            workspace_id=payload.workspace_id or payload.workspace or current_user.workspace_id,
            dataset=payload.dataset,
            dataset_id=payload.dataset_id or payload.dataset,
            selected_dataset_ids=payload.selected_dataset_ids,
            active_project=active_proj,
            project_id=active_proj,
            history=payload.history
        )

        agent_res = await chat_with_agents(agent_payload, current_user, db)
        res_text = agent_res.content or agent_res.response or "I processed your request successfully."

        return ChatMessageResponse(
            role="assistant",
            content=res_text,
            response=res_text,
            thread_id=agent_res.thread_id,
            dataset_id=agent_res.dataset_id,
            dataset_name=agent_res.dataset_name,
            dataset_ids=agent_res.dataset_ids,
            dataset_names=agent_res.dataset_names,
            sql_query=agent_res.sql_query,
            sql=agent_res.sql or agent_res.sql_query,
            data=agent_res.data,
            columns=agent_res.columns,
            row_count=agent_res.row_count,
            execution_time_ms=agent_res.execution_time_ms,
            chart=agent_res.chart,
            table=agent_res.table
        )

