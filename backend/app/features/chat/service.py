from typing import Any, Dict
from app.features.chat.schemas import ChatMessageResponse, ChatMessagePayload


class ChatService:
    """Mock agentic assistant coordinating natural language requests to charts or structured tables."""

    @staticmethod
    def get_assistant_response(payload: ChatMessagePayload) -> ChatMessageResponse:
        text = payload.message.lower()
        res = ChatMessageResponse(
            role="assistant",
            content="I parsed your request successfully. Let me know if you need to run specific database operations.",
        )

        if any(term in text for term in ["forecast", "sales", "chart", "trend"]):
            res = ChatMessageResponse(
                role="assistant",
                content="I queried the active dataset via DuckDB and compiled the monthly sales compared to targets. Here is the chart view:",
                chart={
                    "type": "bar" if "bar" in text else "line",
                    "xKey": "month",
                    "yKeys": ["sales", "target"],
                    "data": [
                        {"month": "Jan", "sales": 4200, "target": 4000},
                        {"month": "Feb", "sales": 4800, "target": 4100},
                        {"month": "Mar", "sales": 5100, "target": 4300},
                        {"month": "Apr", "sales": 4900, "target": 4500},
                        {"month": "May", "sales": 6200, "target": 4800},
                        {"month": "Jun", "sales": 7400, "target": 5000},
                    ],
                },
            )
        elif any(term in text for term in ["segment", "cohort", "cluster", "customer"]):
            res = ChatMessageResponse(
                role="assistant",
                content="I executed a clustering operation on your cohort records. Here are the user profiles clustered by monthly active engagement scores:",
                table={
                    "columns": [
                        {"header": "Cohort Cluster ID", "accessorKey": "cluster"},
                        {"header": "Average engagement", "accessorKey": "engagement"},
                        {"header": "Size (Users)", "accessorKey": "size"},
                    ],
                    "data": [
                        {"cluster": "Cluster Alpha (Power Users)", "engagement": "94.2/100", "size": 1402},
                        {"cluster": "Cluster Beta (Casual)", "engagement": "48.7/100", "size": 6820},
                        {"cluster": "Cluster Gamma (Inactive)", "engagement": "12.4/100", "size": 5982},
                    ],
                },
            )

        return res
