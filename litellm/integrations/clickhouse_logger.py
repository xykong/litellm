import asyncio
import json
import os
from datetime import datetime, timezone
from typing import List, Optional

import litellm
from litellm._logging import verbose_logger
from litellm.integrations.custom_batch_logger import CustomBatchLogger
from litellm.litellm_core_utils.safe_json_dumps import safe_dumps
from litellm.types.integrations.clickhouse import ClickHouseBatchElement
from litellm.types.utils import StandardLoggingPayload


class ClickHouseLogger(CustomBatchLogger):
    def __init__(
        self,
        clickhouse_host: Optional[str] = None,
        clickhouse_port: Optional[int] = None,
        clickhouse_database: Optional[str] = None,
        clickhouse_table: Optional[str] = None,
        clickhouse_username: Optional[str] = None,
        clickhouse_password: Optional[str] = None,
        flush_interval: Optional[int] = None,
        batch_size: Optional[int] = None,
        **kwargs,
    ):
        params = litellm.clickhouse_callback_params or {}

        self.clickhouse_host = (
            clickhouse_host
            or params.get("clickhouse_host")
            or os.environ.get("CLICKHOUSE_HOST", "localhost")
        )
        raw_port = (
            clickhouse_port
            or params.get("clickhouse_port")
            or os.environ.get("CLICKHOUSE_PORT", "8123")
        )
        self.clickhouse_port = int(raw_port)
        self.clickhouse_database = (
            clickhouse_database
            or params.get("clickhouse_database")
            or os.environ.get("CLICKHOUSE_DATABASE", "litellm")
        )
        self.clickhouse_table = (
            clickhouse_table
            or params.get("clickhouse_table")
            or os.environ.get("CLICKHOUSE_TABLE", "spend_logs")
        )
        self.clickhouse_username = (
            clickhouse_username
            or params.get("clickhouse_username")
            or os.environ.get("CLICKHOUSE_USERNAME", "default")
        )
        self.clickhouse_password = (
            clickhouse_password
            or params.get("clickhouse_password")
            or os.environ.get("CLICKHOUSE_PASSWORD", "")
        )

        self.flush_lock = asyncio.Lock()
        asyncio.create_task(self.periodic_flush())

        super().__init__(
            flush_lock=self.flush_lock,
            flush_interval=flush_interval or params.get("flush_interval") or 10,
            batch_size=batch_size or params.get("batch_size") or 100,
        )
        self.log_queue: List[ClickHouseBatchElement] = []

    @property
    def _base_url(self) -> str:
        return f"http://{self.clickhouse_host}:{self.clickhouse_port}"

    def _to_element(
        self,
        payload: StandardLoggingPayload,
    ) -> ClickHouseBatchElement:
        def _ts(dt) -> str:
            if dt is None:
                return ""
            if isinstance(dt, datetime):
                return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            return str(dt)

        def _nullable_ts(dt) -> Optional[str]:
            if dt is None:
                return None
            return _ts(dt)

        metadata = payload.get("metadata") or {}
        return ClickHouseBatchElement(
            request_id=payload.get("id") or "",
            call_type=payload.get("call_type") or "",
            api_key=metadata.get("user_api_key") or "",
            spend=float(payload.get("response_cost") or 0),
            total_tokens=int((payload.get("prompt_tokens") or 0) + (payload.get("completion_tokens") or 0)),
            prompt_tokens=int(payload.get("prompt_tokens") or 0),
            completion_tokens=int(payload.get("completion_tokens") or 0),
            startTime=_ts(payload.get("startTime")),
            endTime=_ts(payload.get("endTime")),
            completionStartTime=_nullable_ts(payload.get("completionStartTime")),
            model=payload.get("model") or "",
            model_id=metadata.get("model_id") or "",
            model_group=payload.get("model_group") or "",
            api_base=payload.get("api_base") or "",
            user=payload.get("user") or "",
            metadata=safe_dumps(metadata),
            cache_hit=str(payload.get("cache_hit") or ""),
            cache_key=metadata.get("cache_key") or "",
            request_tags=safe_dumps(payload.get("request_tags") or []),
            team_id=metadata.get("user_api_key_team_id") or "",
            end_user=payload.get("end_user") or "",
            requester_ip_address=metadata.get("requester_ip_address") or "",
            messages=safe_dumps(payload.get("messages") or []),
            response=safe_dumps(payload.get("response") or {}),
            session_id=metadata.get("session") or "",
        )

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            payload: Optional[StandardLoggingPayload] = kwargs.get("standard_logging_object")
            if payload is None:
                return
            element = self._to_element(payload)
            self.log_queue.append(element)
            if len(self.log_queue) >= self.batch_size:
                await self.flush_queue()
        except Exception:
            verbose_logger.exception("ClickHouseLogger: error in async_log_success_event")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            payload: Optional[StandardLoggingPayload] = kwargs.get("standard_logging_object")
            if payload is None:
                return
            element = self._to_element(payload)
            self.log_queue.append(element)
            if len(self.log_queue) >= self.batch_size:
                await self.flush_queue()
        except Exception:
            verbose_logger.exception("ClickHouseLogger: error in async_log_failure_event")

    async def async_send_batch(self):
        if not self.log_queue:
            return

        rows = list(self.log_queue)
        verbose_logger.debug("ClickHouseLogger: flushing %d rows", len(rows))

        col_names = list(ClickHouseBatchElement.__annotations__.keys())
        tsv_lines = []
        for row in rows:
            values = []
            for col in col_names:
                v = row.get(col)  # type: ignore[call-overload]
                if v is None:
                    values.append("\\N")
                else:
                    values.append(str(v).replace("\t", " ").replace("\n", " "))
            tsv_lines.append("\t".join(values))

        body = "\n".join(tsv_lines)
        query = (
            f"INSERT INTO {self.clickhouse_database}.{self.clickhouse_table} "
            f"({', '.join(col_names)}) FORMAT TabSeparated"
        )

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self._base_url,
                    params={"query": query},
                    content=body.encode("utf-8"),
                    headers={"Content-Type": "text/plain"},
                    auth=(self.clickhouse_username, self.clickhouse_password),
                )
                resp.raise_for_status()
                verbose_logger.debug(
                    "ClickHouseLogger: inserted %d rows, status=%d", len(rows), resp.status_code
                )
        except Exception:
            verbose_logger.exception("ClickHouseLogger: async_send_batch failed")
