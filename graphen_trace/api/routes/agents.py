"""Agent discovery and passive collection selection endpoints."""

from fastapi import APIRouter, HTTPException, Request

from graphen_trace.api.schemas.agents import (
    AgentInstallationResponse,
    AgentListResponse,
    CollectionStartRequest,
)
from graphen_trace.api.schemas.collection import CollectionStatus

router = APIRouter()


@router.get("/agents", response_model=AgentListResponse)
def list_agents(request: Request) -> dict:
    """Returns agent installations found when the local service started."""

    return {
        "items": [
            AgentInstallationResponse(
                name=agent.name,
                path=agent.path,
                version=agent.version,
                adapter=agent.adapter,
            )
            for agent in request.app.state.collection_manager.agents
        ]
    }


@router.post("/collection", response_model=CollectionStatus)
async def start_collection(selection: CollectionStartRequest, request: Request) -> dict:
    """Starts passive collection for an installed supported agent."""

    try:
        return await request.app.state.collection_manager.start(selection.agent)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
