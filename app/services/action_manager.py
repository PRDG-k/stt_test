import os
import json
from functools import lru_cache
from jsonschema import validate, ValidationError
from typing import List, Dict, Any, Optional, Tuple
from pydantic import TypeAdapter, ValidationError as PydanticValidationError
from app.models.schemas import ValidatedAction

SCHEMA_DIR = 'action-definition/schemas'
REGISTRY_FILE = 'action-definition/actions.registry.json'

class ActionManager:
    # 현재 프론트엔드/비즈니스 로직에서 아직 처리하지 못하는 루트 레벨 필드 목록
    IMPLEMENTATION_GAPS = {
        "MOVE_PAGE": ["projectId"],
        "DATA_FETCH": ["status"], # 예시
        "FILE_DOWNLOAD": ["fileType"],
        "DEVICE_CONTROL": ["status"]
    }

    @staticmethod
    @lru_cache(maxsize=1)
    def get_registry() -> Dict[str, Any]:
        if os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"actions": []}

    @staticmethod
    @lru_cache(maxsize=20)
    def load_schema(action_name: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(SCHEMA_DIR, f"{action_name}.schema.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    @classmethod
    def validate_action(cls, action_obj: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        주어진 액션 객체를 검증합니다.
        - 루트 레벨 프로퍼티(Implementation Gaps)는 TBD로 자동 보정합니다.
        - 'params' 내부의 파라미터가 누락되었거나 None(null)인 경우 필드 목록을 반환합니다.
        """
        action_name = action_obj.get("action")
        if not action_name:
            return False, ["action"]
            
        # 1. 루트 레벨 프로퍼티(Implementation Gaps) 자동 보정
        gap_fields = cls.IMPLEMENTATION_GAPS.get(action_name, [])
        for field in gap_fields:
            if field not in action_obj or action_obj.get(field) is None:
                action_obj[field] = "TBD"
        
        # 2. JSON Schema 검증
        schema = cls.load_schema(action_name)
        if not schema:
            return False, ["schema_not_found"]
            
        missing_fields = []
        
        # 명시적으로 null(None)인 파라미터 확인 (Schema validate 이전에 수행)
        params = action_obj.get("params", {})
        if isinstance(params, dict):
            for k, v in params.items():
                if v is None:
                    missing_fields.append(k)
        
        try:
            test_obj = action_obj.copy()
            test_obj.pop("requires_confirmation", None)
            validate(instance=test_obj, schema=schema)
        except ValidationError as e:
            error_path = list(e.path)
            if error_path and error_path[0] == "params":
                field_name = error_path[-1] if len(error_path) > 1 else str(e.message)
                if field_name not in missing_fields:
                    missing_fields.append(field_name)
            elif not error_path:
                # 'required' 제약 조건 위반 등
                msg = str(e.message)
                if "'params'" in msg:
                    missing_fields.append("params")
                else:
                    # 필드명 추출 시도 ('field' is a required property)
                    import re
                    match = re.search(r"'(\w+)' is a required property", msg)
                    if match:
                        missing_fields.append(match.group(1))

        if missing_fields:
            print(f"[Validation Warning] Missing or null parameters in '{action_name}': {missing_fields}")
            return False, list(set(missing_fields))

        # 3. Pydantic 모델 검증
        try:
            TypeAdapter(ValidatedAction).validate_python(action_obj)
            return True, []
        except Exception as e:
            print(f"[Pydantic Partial Error] {e}")
            return True, []

    @classmethod
    def get_all_schemas_text(cls) -> str:
        """
        프롬프트 주입을 위해 모든 스키마 내용을 텍스트로 반환합니다.
        """
        schemas = []
        if os.path.exists(SCHEMA_DIR):
            for filename in sorted(os.listdir(SCHEMA_DIR)):
                if filename.endswith('.json'):
                    path = os.path.join(SCHEMA_DIR, filename)
                    with open(path, 'r', encoding='utf-8') as f:
                        schemas.append(f.read())
        return "\n---\n".join(schemas)

    @classmethod
    def get_dynamic_prompt_context(cls) -> str:
        """
        메타데이터와 DB를 조회하여 LLM에게 줄 최신 제약 조건을 생성합니다.
        현재 시간(KST) 및 날짜 계산 가이드를 포함합니다.
        """
        from datetime import datetime, timedelta, timezone
        
        # KST (UTC+9) 설정
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        
        days = ["월", "화", "수", "목", "금", "토", "일"]
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        day_of_week = days[now.weekday()]
        
        allowed_pages = ["/frontend/dashboard.html", "/analytics", "/settings", "/device-management"]
        active_devices = ["dev_01", "dev_02", "pump_main"]
        
        context = f"""
# 현재 시스템 동적 제약 조건
- MOVE_PAGE 허용 경로: {allowed_pages}
- 현재 제어 가능한 장치 ID: {active_devices}

# 현재 시간 및 날짜 정보 (KST)
- 현재 시각: {now_str} ({day_of_week}요일)

# 날짜 계산 가이드
- "오늘": {now.strftime("%Y-%m-%d")}
- "어제": {(now - timedelta(days=1)).strftime("%Y-%m-%d")}
- "지난 주": 현재 날짜 기준 7일 전부터 오늘까지의 범위, 또는 직전 월~일요일
- "지난 달": 현재 날짜 기준 이전 달의 1일부터 말일까지
- "내일": {(now + timedelta(days=1)).strftime("%Y-%m-%d")} (예약 명령 시 참고)
- 모든 상대적 시간 표현은 위 기준 시각({now_str})을 바탕으로 절대 날짜(YYYY-MM-DD)로 변환하여 파라미터에 채우세요.
"""
        return context

action_manager = ActionManager()
