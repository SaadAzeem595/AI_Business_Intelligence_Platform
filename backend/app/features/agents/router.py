import os
import re
import uuid
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser, require_role
from app.features.agents.schemas import AgentChatPayload, ApproveQueryPayload, AgentChatResponse, ExecutionLogItem
from app.features.agents.graph import agent_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["LangGraph Multi-Agent Platform"])


def auto_detect_dataset_from_query(
    user_query: str,
    available_datasets: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], str]:
    """
    Performs multi-stage deterministic + semantic auto-detection:
    1. Exact / substring match of dataset filename, display_name, duckdb_table, or base name in query.
    2. Word token match.
    3. Column / Schema name matching with semantic synonyms.
    Returns: (detected_dataset, candidate_matches, detection_mode)
    """
    if not available_datasets:
        return None, [], "none_available"

    if len(available_datasets) == 1:
        return available_datasets[0], available_datasets, "single_available"

    q_lower = user_query.lower()
    q_tokens = set(re.findall(r'[a-zA-Z0-9]+', q_lower))

    # Stage 1: Exact / Substring filename or table match in query
    stage1_candidates = []
    for ds in available_datasets:
        fn = (ds.get("filename") or "").lower()
        disp = (ds.get("display_name") or "").lower()
        tbl = (ds.get("duckdb_table") or "").lower()
        base = os.path.splitext(fn)[0].lower() if fn else ""

        if (fn and fn in q_lower) or (disp and disp in q_lower) or (tbl and tbl in q_lower) or (base and len(base) > 3 and base in q_lower):
            stage1_candidates.append(ds)

    if len(stage1_candidates) == 1:
        return stage1_candidates[0], stage1_candidates, "exact_name_match"
    elif len(stage1_candidates) > 1:
        return None, stage1_candidates, "multiple_name_matches"

    # Stage 2: Token match (e.g. 'olist', 'geolocation')
    stage2_candidates = []
    stopwords = {"csv", "xlsx", "json", "parquet", "dataset", "table", "data", "file", "records", "the", "in", "and", "or", "of", "to", "for"}
    for ds in available_datasets:
        fn = (ds.get("filename") or "").lower()
        disp = (ds.get("display_name") or "").lower()
        tbl = (ds.get("duckdb_table") or "").lower()
        name_tokens = (set(re.findall(r'[a-zA-Z0-9]+', f"{fn} {disp} {tbl}")) - stopwords)
        if name_tokens:
            overlap = name_tokens & q_tokens
            if len(overlap) >= 2 or (len(name_tokens) == 1 and overlap):
                stage2_candidates.append(ds)

    if len(stage2_candidates) == 1:
        return stage2_candidates[0], stage2_candidates, "token_match"
    elif len(stage2_candidates) > 1:
        return None, stage2_candidates, "multiple_token_matches"

    # Stage 3: Column / Schema name matching with semantic synonyms
    synonyms = {
        "lat": ["latitude"],
        "latitude": ["lat", "geolocation_lat"],
        "lng": ["longitude"],
        "lon": ["longitude"],
        "longitude": ["lng", "lon", "geolocation_lng"],
        "zip": ["zip_code", "zipcode", "postal_code", "prefix"],
        "city": ["city", "town", "municipality"],
        "state": ["state", "province", "region"],
        "price": ["cost", "amount", "charge", "sales", "revenue"],
        "score": ["rating", "stars", "feedback"],
        "customer": ["client", "buyer", "user"],
        "order": ["purchase", "transaction"],
    }

    col_scores = []
    for ds in available_datasets:
        cols = []
        c_raw = ds.get("columns_json")
        if c_raw:
            try:
                import json
                cols = json.loads(c_raw) if isinstance(c_raw, str) else c_raw
            except Exception:
                cols = []
        if not cols and ds.get("schema_json"):
            try:
                import json
                s_dict = json.loads(ds["schema_json"]) if isinstance(ds["schema_json"], str) else ds["schema_json"]
                cols = list(s_dict.keys())
            except Exception:
                cols = []

        score = 0
        for col in cols:
            col_str = str(col).lower()
            col_parts = set(re.findall(r'[a-zA-Z0-9]+', col_str))
            if col_str in q_lower:
                score += 4
            elif any(part in q_tokens and len(part) > 2 for part in col_parts):
                score += 2

            for syn_key, syn_vals in synonyms.items():
                if syn_key in col_parts or col_str == syn_key:
                    if any(sv in q_tokens or sv in q_lower for sv in syn_vals):
                        score += 3

        if score > 0:
            col_scores.append((score, ds))

    if col_scores:
        col_scores.sort(key=lambda x: x[0], reverse=True)
        top_score, top_ds = col_scores[0]
        if len(col_scores) == 1 or top_score >= col_scores[1][0] + 2:
            return top_ds, [top_ds], "schema_match"
        elif len(col_scores) > 1 and top_score == col_scores[1][0]:
            candidates = [ds for s, ds in col_scores if s == top_score]
            return None, candidates, "multiple_schema_matches"

    # Default fallback to first available
    return available_datasets[0], available_datasets, "default_fallback"


def build_response_from_state(thread_id: str, graph_state: Any, execution_time_ms: Optional[float] = None) -> AgentChatResponse:
    state_values = graph_state.values if graph_state else {}
    next_nodes = graph_state.next if graph_state else []
    
    # Map execution logs to ExecutionLogItem schemas
    raw_logs = state_values.get("execution_logs", [])
    logs = [
        ExecutionLogItem(
            agent_name=log.get("agent_name"),
            status=log.get("status"),
            duration_ms=log.get("duration_ms"),
            timestamp=log.get("timestamp"),
            details=log.get("details")
        )
        for log in raw_logs
    ]
    
    status_str = "completed"
    if next_nodes:
        status_str = "paused"
        
    # Build Table
    table = None
    sql_result = state_values.get("sql_result")
    if sql_result and isinstance(sql_result, dict) and "columns" in sql_result and "rows" in sql_result:
        table = {
            "columns": [{"header": col, "accessorKey": col} for col in sql_result["columns"]],
            "data": sql_result["rows"]
        }
    
    analytics_result = state_values.get("analytics_result")
    if not table and analytics_result and isinstance(analytics_result, dict) and "columns" in analytics_result:
        cols = analytics_result["columns"]
        if isinstance(cols, dict):
            table_rows = []
            for col_name, prof in cols.items():
                table_rows.append({
                    "column": col_name,
                    "type": prof.get("type", "unknown"),
                    "missing": prof.get("missing_count", 0),
                    "completeness": f"{prof.get('completeness', 100.0):.1f}%",
                    "cardinality": prof.get("cardinality", 0)
                })
            table = {
                "columns": [
                    {"header": "Column Name", "accessorKey": "column"},
                    {"header": "Data Type", "accessorKey": "type"},
                    {"header": "Missing Count", "accessorKey": "missing"},
                    {"header": "Completeness", "accessorKey": "completeness"},
                    {"header": "Distinct Values", "accessorKey": "cardinality"}
                ],
                "data": table_rows
            }

    # Build Chart
    chart = None
    vis_spec = state_values.get("visualization_spec")
    if vis_spec and isinstance(vis_spec, dict):
        if "data" in vis_spec and "values" in vis_spec["data"]:
            data = vis_spec["data"]["values"]
            x_key = None
            y_keys = []
            if "encoding" in vis_spec:
                encoding = vis_spec["encoding"]
                if "x" in encoding and "field" in encoding["x"]:
                    x_key = encoding["x"]["field"]
                if "y" in encoding and "field" in encoding["y"]:
                    y_keys.append(encoding["y"]["field"])
            if not x_key and data and len(data) > 0:
                keys = list(data[0].keys())
                x_key = keys[0]
                y_keys = keys[1:]
            chart = {
                "type": vis_spec.get("mark", "bar"),
                "data": data,
                "xKey": x_key or "category",
                "yKeys": y_keys or ["value"]
            }
        elif "series" in vis_spec and isinstance(vis_spec["series"], list):
            data = []
            x_key = vis_spec.get("xAxis", {}).get("name", "category")
            y_keys = [s["name"] for s in vis_spec["series"]]
            x_data = vis_spec["xAxis"].get("data", [])
            for idx, x_val in enumerate(x_data):
                row = {x_key: x_val}
                for s in vis_spec["series"]:
                    if idx < len(s["data"]):
                        row[s["name"]] = s["data"][idx]
                data.append(row)
            chart = {
                "type": vis_spec.get("chart_type", "line"),
                "data": data,
                "xKey": x_key,
                "yKeys": y_keys
            }

    final_resp = state_values.get("final_response") or "I processed your request successfully."

    data_rows = None
    data_cols = None
    data_count = None
    if sql_result and isinstance(sql_result, dict) and "rows" in sql_result:
        data_rows = sql_result.get("rows")
        data_cols = sql_result.get("columns")
        data_count = len(data_rows) if data_rows is not None else 0

    dataset_id = state_values.get("dataset_id")
    dataset_name = state_values.get("dataset")
    dataset_ids = [dataset_id] if dataset_id else []
    dataset_names = [dataset_name] if dataset_name else []
    sql_q = state_values.get("sql_query")

    logger.info(
        f"AI_CHAT_RESPONSE_COMPILED: user_id={state_values.get('user_id')} "
        f"project_id={state_values.get('active_project')} dataset_id={dataset_id} "
        f"sql_executed='{sql_q}' row_count={data_count} "
        f"response_len={len(final_resp)}"
    )

    return AgentChatResponse(
        thread_id=thread_id,
        status=status_str,
        response=final_resp,
        content=final_resp,
        reasoning_path=state_values.get("reasoning_path", []),
        execution_logs=logs,
        visualization_spec=state_values.get("visualization_spec"),
        recommendations=state_values.get("recommendations"),
        executive_summary=state_values.get("executive_summary"),
        sql_query=sql_q,
        sql=sql_q,
        chart=chart,
        table=table,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        dataset_ids=dataset_ids,
        dataset_names=dataset_names,
        data=data_rows,
        columns=data_cols,
        row_count=data_count,
        execution_time_ms=execution_time_ms or state_values.get("execution_time_ms")
    )



@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agents(
    payload: AgentChatPayload,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> AgentChatResponse:
    """Sends a query to the multi-agent planning & execution graph, preserving session memory."""
    if not payload.message or not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User query message cannot be empty."
        )

    active_proj = payload.active_project or payload.project_id
    thread_id = payload.thread_id or payload.conversation_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    logger.info(
        f"REQUEST_RECEIVED: user_id={current_user.id} project_id={active_proj} "
        f"dataset_id={payload.dataset_id or payload.dataset} thread_id={thread_id} "
        f"message='{payload.message}'"
    )

    try:
        import time
        import traceback
        from app.core.telemetry import LANGGRAPH_LATENCY
        from sqlalchemy import select
        from app.features.datasets.models import Dataset
        
        # 1. Thread context recovery & conversation memory
        current_state = agent_graph.get_state(config)
        start_time = time.perf_counter()
        
        prev_dataset_id = current_state.values.get("dataset_id") if current_state and current_state.values else None
        prev_dataset = current_state.values.get("dataset") if current_state and current_state.values else None
        prev_project_id = current_state.values.get("active_project") if current_state and current_state.values else None

        if not active_proj and prev_project_id:
            active_proj = prev_project_id

        # 2. Extract requested dataset name or ID
        from sqlalchemy import func
        from app.features.agents.agents import extract_requested_dataset_name
        
        target_ds_id = payload.dataset_id or payload.dataset
        if not target_ds_id and payload.message:
            extracted = extract_requested_dataset_name(payload.message)
            if extracted:
                target_ds_id = extracted

        target_ds = None
        if target_ds_id and target_ds_id not in ("all", "auto"):
            clean_target = str(target_ds_id).strip()
            clean_base = os.path.splitext(clean_target)[0].lower()
            try:
                ds_stmt = select(Dataset).where(
                    (Dataset.id == clean_target)
                    | (func.lower(Dataset.filename) == clean_target.lower())
                    | (func.lower(Dataset.display_name) == clean_target.lower())
                    | (func.lower(Dataset.duckdb_table) == clean_target.lower())
                    | (func.lower(Dataset.filename) == f"{clean_base}.csv")
                    | (func.lower(Dataset.display_name) == clean_base)
                    | (func.lower(Dataset.duckdb_table) == clean_base)
                    | (Dataset.duckdb_table.ilike(f"%{clean_base}%"))
                )
                ds_res = await db.execute(ds_stmt)
                target_ds = ds_res.scalars().first()
                if target_ds and not active_proj and target_ds.project_id:
                    active_proj = target_ds.project_id
                    logger.info(f"INFERRED_ACTIVE_PROJECT: project_id={active_proj} from dataset={target_ds.filename}")
            except Exception as dse:
                logger.warning(f"Could not infer target dataset: {dse}")

        # 3. Load accessible datasets
        if active_proj:
            try:
                from app.features.projects.router import get_project_and_verify_access
                await get_project_and_verify_access(active_proj, current_user, db)
                stmt = select(Dataset).where(Dataset.project_id == active_proj)
                logger.info(f"PROJECT_RESOLVED: project_id={active_proj}")
            except Exception as pe:
                logger.warning(f"PROJECT_LOOKUP_FAILED: active_project={active_proj} access error: {pe}")
                stmt = select(Dataset).where(Dataset.project_id == active_proj)
        else:
            logger.info("PROJECT_RESOLVED: project_id=None (Workspace global mode)")
            ws_candidates = {"default"}
            if getattr(current_user, "workspace_id", None):
                ws_candidates.add(str(current_user.workspace_id))
            if getattr(payload, "workspace_id", None):
                ws_candidates.add(str(payload.workspace_id))
            if getattr(payload, "workspace", None):
                ws_candidates.add(str(payload.workspace))

            stmt = select(Dataset).where(
                (Dataset.workspace_id.in_(list(ws_candidates)))
                | (Dataset.workspace_id == None)
                | (Dataset.owner_id == getattr(current_user, "id", None))
            )

        if getattr(payload, "available_datasets", None):
            available_datasets = payload.available_datasets
        else:
            result = await db.execute(stmt)
            db_items = list(result.scalars().all())

            # Resilient fallback: If db_items is empty in workspace global mode, query all datasets
            if not db_items and not active_proj:
                fallback_res = await db.execute(select(Dataset))
                db_items = list(fallback_res.scalars().all())

            # If an explicit target dataset was found and isn't in db_items (e.g. project scoping mismatch), include it
            if target_ds:
                existing_ids = {str(item.id) if hasattr(item, "id") else str(item["id"]) for item in db_items}
                target_id = str(target_ds.id) if hasattr(target_ds, "id") else str(target_ds["id"])
                if target_id not in existing_ids:
                    db_items.append(target_ds)

            available_datasets = [
                {
                    "id": str(item.id) if hasattr(item, "id") else str(item["id"]),
                    "filename": item.filename if hasattr(item, "filename") else item.get("filename"),
                    "display_name": item.display_name if hasattr(item, "display_name") else item.get("display_name"),
                    "storage_path": item.storage_path if hasattr(item, "storage_path") else item.get("storage_path"),
                    "duckdb_table": item.duckdb_table if hasattr(item, "duckdb_table") else item.get("duckdb_table"),
                    "type": item.type if hasattr(item, "type") else item.get("type"),
                    "columns_json": item.columns_json if hasattr(item, "columns_json") else item.get("columns_json"),
                    "schema_json": item.schema_json if hasattr(item, "schema_json") else item.get("schema_json"),
                    "rows": item.rows if hasattr(item, "rows") else item.get("rows"),
                    "status": item.status if hasattr(item, "status") else item.get("status"),
                    "project_id": item.project_id if hasattr(item, "project_id") else item.get("project_id"),
                }
                for item in db_items
            ]

        # 4. Storage path verification across candidate upload directories
        from app.core.config import settings
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        cand_dirs = [
            getattr(settings, "resolved_uploads_dir", None),
            os.path.join(os.getcwd(), "uploads"),
            os.path.join(os.getcwd(), "backend", "uploads"),
            os.path.join(os.getcwd(), "backend", "app", "uploads"),
            os.path.join(os.getcwd(), "app", "uploads"),
            os.path.join(root_dir, "uploads"),
            os.path.join(root_dir, "backend", "uploads"),
            os.path.join(root_dir, "backend", "app", "uploads"),
            "/app/uploads",
            "/app/app/uploads",
            "/app/backend/uploads",
            "/app/backend/app/uploads",
        ]
        for ds in available_datasets:
            sp = ds.get("storage_path")
            fn = ds.get("filename")
            orig = ds.get("original_filename")
            if not sp or not os.path.exists(sp):
                candidate_fns = [f for f in [fn, os.path.basename(sp) if sp else None, orig] if f]
                for candidate_fn in candidate_fns:
                    for cdir in cand_dirs:
                        if cdir and os.path.isdir(cdir):
                            target_file = os.path.join(cdir, candidate_fn)
                            if os.path.exists(target_file):
                                ds["storage_path"] = target_file
                                break
                            # Also check files with UUID prefix
                            try:
                                for actual_f in os.listdir(cdir):
                                    if actual_f == candidate_fn or actual_f.endswith(f"_{candidate_fn}") or actual_f.lower().endswith(candidate_fn.lower()):
                                        ds["storage_path"] = os.path.join(cdir, actual_f)
                                        break
                            except Exception:
                                pass
                            if ds.get("storage_path") and os.path.exists(ds["storage_path"]):
                                break
                    if ds.get("storage_path") and os.path.exists(ds["storage_path"]):
                        break

        # 5. Multi-stage auto-detection & clarification check
        detection_mode = "manual" if target_ds else "auto_detect"
        if not target_ds:
            # Check conversation memory for follow-up questions
            extracted = extract_requested_dataset_name(payload.message) if payload.message else None
            if not extracted and prev_dataset_id:
                for ds in available_datasets:
                    if ds.get("id") == prev_dataset_id or ds.get("filename") == prev_dataset:
                        target_ds = ds
                        detection_mode = "conversation_memory"
                        break

            # If still unresolved, run multi-stage auto-detection
            if not target_ds:
                detected, candidates, mode = auto_detect_dataset_from_query(payload.message, available_datasets)
                detection_mode = mode
                if detected:
                    target_ds = detected
                elif candidates and mode.startswith("multiple"):
                    candidate_names = [d.get("display_name") or d.get("filename") for d in candidates]
                    clarification_msg = (
                        f"I found multiple datasets matching your question: {', '.join(candidate_names)}. "
                        "Please select which dataset you would like to analyze from the dropdown or mention it directly in your message."
                    )
                    logger.info(f"MULTIPLE_DATASETS_MATCHED: candidates={candidate_names}")
                    return AgentChatResponse(
                        thread_id=thread_id,
                        status="needs_clarification",
                        response=clarification_msg,
                        content=clarification_msg,
                        reasoning_path=["dataset_auto_detector"],
                        execution_logs=[
                            ExecutionLogItem(
                                agent_name="dataset_auto_detector",
                                status="needs_clarification",
                                duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
                                timestamp=datetime.now().isoformat(),
                                details=f"Multiple candidates matched: {candidate_names}"
                            )
                        ],
                        dataset_names=candidate_names,
                        dataset_ids=[str(d.get("id")) for d in candidates]
                    )

        # 6. Final resolution metadata logging
        resolved_ds_id = None
        resolved_ds_fn = None
        if target_ds:
            resolved_ds_id = str(target_ds.get("id")) if isinstance(target_ds, dict) else str(target_ds.id)
            resolved_ds_fn = target_ds.get("filename") if isinstance(target_ds, dict) else target_ds.filename
            t_proj = target_ds.get("project_id") if isinstance(target_ds, dict) else target_ds.project_id
            if t_proj and not active_proj:
                active_proj = t_proj

        logger.info(
            f"CHAT_DATASET_RESOLUTION: mode={detection_mode} resolved_id={resolved_ds_id} "
            f"resolved_file='{resolved_ds_fn}' active_project={active_proj}"
        )
        logger.info(f"DATASETS_LOADED: project_id={active_proj} count={len(available_datasets)} datasets={[d['filename'] for d in available_datasets]}")
        logger.info(f"SCHEMA_LOADED: tables={[d['duckdb_table'] for d in available_datasets]}")

        # Run or update agent graph
        if not current_state or not current_state.values:
            initial_state = {
                "query": payload.message,
                "workspace": current_user.workspace_id,
                "dataset": resolved_ds_fn or payload.dataset_id or payload.dataset,
                "selected_dataset_ids": payload.selected_dataset_ids,
                "available_datasets": available_datasets,
                "active_project": active_proj,
                "history": payload.history or [],
                "plan": [],
                "completed_steps": [],
                "next_agent": "",
                "sql_query": None,
                "sql_result": None,
                "analytics_result": None,
                "ml_result": None,
                "forecast_result": None,
                "rag_result": None,
                "visualization_spec": None,
                "recommendations": None,
                "executive_summary": None,
                "final_response": None,
                "is_approved": True,
                "execution_logs": [],
                "reasoning_path": [],
                "workspace_id": current_user.workspace_id,
                "dataset_id": resolved_ds_id or payload.dataset_id or payload.dataset,
                "dataset_context": None,
                "dataset_schema": None,
                "user_message": payload.message,
                "intent": None,
                "generated_sql": None,
                "errors": [],
                "user_id": current_user.id,
                "roles": [current_user.role],
            }
            agent_graph.invoke(initial_state, config)
        else:
            agent_graph.update_state(config, {
                "query": payload.message,
                "dataset": resolved_ds_fn or payload.dataset_id or payload.dataset,
                "selected_dataset_ids": payload.selected_dataset_ids,
                "available_datasets": available_datasets,
                "active_project": active_proj,
                "history": payload.history or [],
                "plan": [],
                "completed_steps": [],
                "next_agent": "",
                "sql_query": None,
                "sql_result": None,
                "analytics_result": None,
                "ml_result": None,
                "forecast_result": None,
                "rag_result": None,
                "visualization_spec": None,
                "recommendations": None,
                "executive_summary": None,
                "final_response": None,
                "generated_sql": None,
                "execution_logs": [],
                "reasoning_path": [],
                "errors": [],
                "workspace_id": current_user.workspace_id,
                "dataset_id": resolved_ds_id or payload.dataset_id or payload.dataset,
                "user_message": payload.message,
                "intent": None,
                "user_id": current_user.id,
                "roles": [current_user.role],
                "is_approved": True,
            }, as_node="__start__")
            agent_graph.invoke(None, config)
            
        duration = time.perf_counter() - start_time
        LANGGRAPH_LATENCY.labels(thread_id=thread_id).observe(duration)
        exec_ms = round(duration * 1000, 2)
        
        final_state = agent_graph.get_state(config)
        resp = build_response_from_state(thread_id, final_state, execution_time_ms=exec_ms)
        logger.info(f"REQUEST_COMPLETED: thread_id={thread_id} exec_ms={exec_ms}")
        return resp
        
    except HTTPException:
        raise
    except Exception as e:
        err_tb = traceback.format_exc()
        logger.error(f"REQUEST_FAILED: stage=AGENT_GRAPH_EXECUTION error='{str(e)}'\n{err_tb}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": f"AI Chat execution error: {str(e)}",
                "stage": "AGENT_GRAPH_EXECUTION",
                "details": str(e)
            }
        )



@router.post("/approve", response_model=AgentChatResponse)
async def approve_pending_agent_action(
    payload: ApproveQueryPayload,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"]))
) -> AgentChatResponse:
    """Approves (or skips) SQL execution on an active paused thread, resuming graph flow."""
    thread_id = payload.thread_id
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        current_state = agent_graph.get_state(config)
        if not current_state or not current_state.next:
            raise ValueError("No pending paused nodes found for this thread ID.")
            
        state_values = current_state.values
        
        if payload.approved:
            logger.info(f"User approved SQL action on thread {thread_id}. Resuming execution.")
            # Set is_approved to True, resuming sql_agent node
            agent_graph.update_state(config, {"is_approved": True})
            agent_graph.invoke(None, config)
        else:
            logger.info(f"User skipped SQL action on thread {thread_id}. Marking step completed and resuming.")
            # Bypass sql_agent by adding it to completed steps
            completed = list(state_values.get("completed_steps", []))
            completed.append("sql_agent")
            agent_graph.update_state(config, {"completed_steps": completed, "is_approved": False}, as_node="sql_agent")
            agent_graph.invoke(None, config)
            
        final_state = agent_graph.get_state(config)
        return build_response_from_state(thread_id, final_state)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval resumption failed: {str(e)}"
        )
