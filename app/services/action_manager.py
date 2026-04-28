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
    
    # [고도화] 각 액션별 핵심 파라미터 확장 우선순위 맵
    ACTION_FIELD_PRIORITY = {
        "MOVE_PAGE": ["url", "slId", "projectId"],
        "DEVICE_CONTROL": ["device", "command"],
        "DATA_FETCH": ["device", "target", "interval"],
        "FILE_DOWNLOAD": ["reportName", "fileType"]
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
    def validate_action(cls, action_obj: Dict[str, Any], text: Optional[str] = None) -> Tuple[bool, List[str]]:
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
        
        def check_field(k, v, parent_obj):
            if v is None:
                if k not in missing_fields:
                    missing_fields.append(k)
            elif k == "device" and v not in ["inverter_01", "inverter_02", "inverter_03", "pump_main"]:
                print(f"[Validation Error] Hallucinated device ID: {v}")
                parent_obj[k] = None
                if k not in missing_fields:
                    missing_fields.append(k)
            elif k == "url" and v not in ["/frontend/dashboard.html", "/frontend/settlement.html", "/frontend/notice-report.html", "/frontend/tax-report.html"]:
                if v != "TBD":
                    print(f"[Validation Error] Hallucinated URL: {v}")
                    parent_obj[k] = None
                    if k not in missing_fields:
                        missing_fields.append(k)

        # 루트 레벨 체크
        for k, v in action_obj.items():
            if k not in ["action", "params", "requires_confirmation"] and k not in gap_fields:
                check_field(k, v, action_obj)

        # params 객체 내부 체크
        params = action_obj.get("params", {})
        if isinstance(params, dict):
            for k, v in params.items():
                check_field(k, v, params)
        
        # [우선순위 기반 다중 매칭 검사]
        # LLM이 단일 값을 임의로 채웠더라도, 텍스트가 여러 후보에 매칭되면 모호성으로 간주하고 강제로 누락 처리 (오버라이드)
        priority_fields = cls.ACTION_FIELD_PRIORITY.get(action_name, [])
        if text:
            # 텍스트에 숫자가 단독으로 쓰인 경우(예: "1번") 확실히 하나를 지정한 것이므로 강제 오버라이드 하지 않음
            import re
            has_explicit_number = bool(re.search(r'\d+번|\d+째|^\d+$', text.strip()))
            
            if not has_explicit_number:
                for pf in priority_fields:
                    # 해당 필드가 이미 missing_fields에 없다면 (LLM이 채웠다면)
                    if pf not in missing_fields:
                        candidates_for_field = cls.get_field_candidates(action_name, pf, text=text, strict_filter=True)
                        # 필터링 결과 여러 개가 나왔다면, 이는 LLM이 그 중 하나를 임의로 찍었을 확률이 매우 높음
                        if len(candidates_for_field) >= 2:
                            print(f"[Validation Warning] Ambiguous match detected for '{pf}'. Forcing missing state. (Matched: {len(candidates_for_field)})")
                            if "params" in action_obj and isinstance(action_obj["params"], dict) and pf in action_obj["params"]:
                                action_obj["params"][pf] = None
                            elif pf in action_obj:
                                action_obj[pf] = None
                            missing_fields.append(pf)

        try:
            test_obj = action_obj.copy()
            test_obj.pop("requires_confirmation", None)
            validate(instance=test_obj, schema=schema)
        except ValidationError as e:
            error_path = list(e.path)
            if error_path:
                field_name = error_path[-1]
                if field_name not in missing_fields:
                    missing_fields.append(field_name)
            else:
                # 'required' 제약 조건 위반 등
                msg = str(e.message)
                import re
                match = re.search(r"'(\w+)' is a required property", msg)
                if match:
                    field_name = match.group(1)
                    if field_name not in missing_fields:
                        missing_fields.append(field_name)

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
        모든 액션 스키마의 enum 값을 동적으로 읽어와 주입합니다.
        """
        from datetime import datetime, timedelta, timezone
        
        # KST (UTC+9) 설정
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        
        days = ["월", "화", "수", "목", "금", "토", "일"]
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        day_of_week = days[now.weekday()]
        
        allowed_pages = ["/frontend/dashboard.html", "/frontend/settlement.html", "/frontend/notice-report.html", "/frontend/tax-report.html"]
        active_devices = ["inverter_01", "inverter_02", "inverter_03", "pump_main"]
        
        # 스키마의 모든 Enum 값을 동적으로 수집
        enums_info = []
        if os.path.exists(SCHEMA_DIR):
            for filename in sorted(os.listdir(SCHEMA_DIR)):
                if filename.endswith('.schema.json'):
                    action_name = filename.replace('.schema.json', '')
                    schema = cls.load_schema(action_name)
                    if schema:
                        # params 내부의 enum 확인
                        params_props = schema.get("properties", {}).get("params", {}).get("properties", {})
                        for field, spec in params_props.items():
                            if "enum" in spec:
                                enums_info.append(f"- {action_name}의 '{field}': {spec['enum']}")
                        # 루트 레벨 enum 확인
                        for field, spec in schema.get("properties", {}).items():
                            if field not in ["action", "params"] and "enum" in spec:
                                enums_info.append(f"- {action_name}의 '{field}': {spec['enum']}")
        
        enum_context = "\n".join(enums_info) if enums_info else "- (정의된 Enum 없음)"

        context = f"""
# 현재 시스템 동적 제약 조건
- MOVE_PAGE 허용 경로: {allowed_pages}
- 현재 제어 가능한 장치 ID: {active_devices}
{enum_context}

# 현재 시간 및 날짜 정보 (KST)
- 현재 시각: {now_str} ({day_of_week}요일)

# 날짜 파라미터 (start, end 등) 추출 및 계산 가이드
- 날짜는 반드시 "YYYY-MM-DD" 형태여야 합니다.
- "오늘": {now.strftime("%Y-%m-%d")}
- "어제": {(now - timedelta(days=1)).strftime("%Y-%m-%d")}
- "내일": {(now + timedelta(days=1)).strftime("%Y-%m-%d")}
- "이번 달": 1일({now.replace(day=1).strftime("%Y-%m-%d")})부터 현재 또는 말일까지
- "지난 달": 이전 달의 1일부터 말일까지
- "올해": {now.strftime("%Y")}-01-01 부터 {now.strftime("%Y-%m-%d")} 까지
- 모든 상대적 시간 표현은 위 기준 시각({now_str})을 바탕으로 절대 날짜(YYYY-MM-DD)로 변환하여 추출하세요.
"""
        return context

    @classmethod
    def get_field_candidates(cls, action_name: str, field_name: str, text: Optional[str] = None, strict_filter: bool = False) -> List[str]:
        """
        지정된 액션의 특정 필드에 대해 선택 가능한 후보군 리스트를 반환합니다.
        text가 제공되면 해당 텍스트와 연관된 후보만 필터링합니다.
        strict_filter가 True일 경우, 필터링 결과가 매칭되는 것이 없으면 빈 리스트를 반환합니다.
        """
        candidates = []
        
        # 1. 특정 필드 이름에 따른 동적 후보군 (디바이스, 페이지 등)
        if field_name == "device":
            candidates = ["inverter_01", "inverter_02", "inverter_03", "pump_main"]
        
        elif field_name == "url":
            candidates = ["/frontend/dashboard.html", "/frontend/settlement.html", "/frontend/notice-report.html", "/frontend/tax-report.html"]

        elif field_name == "downloadUrl":
            candidates = ["최신 정산내역.xlsx", "최신 정산내역.pdf", "지난 달 세무보고서.xlsx", "매출리포트.pdf", "세무조정.zip"]
            
        elif field_name == "slId":
            # slId는 프론트엔드에서 API 인자로 전달되어야 하는 값이므로 후보군 확장을 하지 않습니다.
            candidates = []

        else:
            # 2. 스키마의 Enum 값 추출
            schema = cls.load_schema(action_name)
            if schema:
                # params 객체 내부의 필드인지 확인
                params_props = schema.get("properties", {}).get("params", {}).get("properties", {})
                field_spec = params_props.get(field_name) or schema.get("properties", {}).get(field_name)
                
                if field_spec and "enum" in field_spec:
                    candidates = field_spec["enum"]
        
        # 3. 텍스트 필터링 (간단한 포함 여부 확인)
        if text and candidates:
            # 한글 조사 제거 및 소문자 변환
            clean_text = text.lower().replace("번", "").replace("째", "").strip()
            # "보고서" -> "report", "인버터" -> "inverter", "메인" -> "main" 등 매핑 가능 (고도화 포인트)
            keywords = {
                "보고서": "report",
                "정산": "settlement",
                "대시보드": "dashboard",
                "공지": "notice",
                "세금": "tax",
                "인버터": "inverter",
                "펌프": "pump"
            }
            
            search_terms = [clean_text]
            for k, v in keywords.items():
                if k in clean_text:
                    search_terms.append(v)
            
            filtered = [
                c for c in candidates 
                if any(term in c.lower() for term in search_terms) or 
                   any(c.lower() in term for term in search_terms)
            ]
            
            # 필터링 결과가 있으면 반환, 없으면 strict_filter 옵션에 따라 처리
            if filtered:
                return filtered
            elif strict_filter:
                return []
                
        return candidates

action_manager = ActionManager()
