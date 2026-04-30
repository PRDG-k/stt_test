import os
import json
from functools import lru_cache
from jsonschema import validate, ValidationError
from typing import List, Dict, Any, Optional, Tuple
from pydantic import TypeAdapter, ValidationError as PydanticValidationError
from app.models.schemas import ValidatedAction

SCHEMA_DIR = 'action-definition/schemas'
METADATA_DIR = 'action-definition/metadata'
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
        "MOVE_PAGE": ["url", "slId", "year", "projectId"],
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

    @staticmethod
    @lru_cache(maxsize=20)
    def load_metadata(action_name: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(METADATA_DIR, f"{action_name}.meta.json")
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
        
        # 메타데이터 기반 동적 검증 (예: MOVE_PAGE의 URL별 필수 파라미터)
        metadata = cls.load_metadata(action_name)
        if action_name == "MOVE_PAGE" and metadata:
            url = action_obj.get("url")
            pages_config = metadata.get("pages", {})
            if url in pages_config:
                page_meta = pages_config[url]
                required_params = page_meta.get("required_params", [])
                params = action_obj.get("params", {})
                for rp in required_params:
                    # params 내부에 있거나 루트에 있는 경우 체크
                    val = params.get(rp) if isinstance(params, dict) else action_obj.get(rp)
                    if val is None or val == "":
                        if rp not in missing_fields:
                            missing_fields.append(rp)

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
        priority_fields = cls.ACTION_FIELD_PRIORITY.get(action_name, [])
        if text:
            import re
            has_explicit_number = bool(re.search(r'\d+번|\d+째|^\d+$', text.strip()))
            
            if not has_explicit_number:
                for pf in priority_fields:
                    if pf not in missing_fields:
                        candidates_for_field = cls.get_field_candidates(action_name, pf, text=text, action_obj=action_obj, strict_filter=True)
                        if len(candidates_for_field) >= 2:
                            print(f"[Validation Warning] Ambiguous match detected for '{pf}'. Forcing missing state.")
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
            # Schema validation error handling... (생략)
            pass

        if missing_fields:
            return False, list(set(missing_fields))

        return True, []

    @classmethod
    def get_all_schemas_text(cls) -> str:
        # (생략)
        pass

    @classmethod
    def get_dynamic_prompt_context(cls) -> str:
        # (생략)
        pass

    @classmethod
    def get_field_candidates(cls, action_name: str, field_name: str, text: Optional[str] = None, action_obj: Optional[Dict[str, Any]] = None, strict_filter: bool = False) -> List[str]:
        """
        지정된 액션의 특정 필드에 대해 선택 가능한 후보군 리스트를 반환합니다.
        메타데이터 설정을 최우선으로 참조합니다.
        """
        candidates = []
        metadata = cls.load_metadata(action_name)
        
        # 1. 메타데이터 기반 동적 후보군 (특히 MOVE_PAGE의 URL별 파라미터)
        if action_name == "MOVE_PAGE" and metadata:
            url = action_obj.get("url") if action_obj else None
            pages_config = metadata.get("pages", {})
            if url in pages_config:
                params_config = pages_config[url].get("params_config", {})
                if field_name in params_config:
                    candidates = params_config[field_name].get("candidates", [])

        # 2. 기존 하드코딩된 글로벌 후보군 (Fallback)
        if not candidates:
            if field_name == "device":
                candidates = ["inverter_01", "inverter_02", "inverter_03", "pump_main"]
            elif field_name == "url":
                candidates = ["/frontend/dashboard.html", "/frontend/settlement.html", "/frontend/notice-report.html", "/frontend/tax-report.html"]
            else:
                schema = cls.load_schema(action_name)
                if schema:
                    params_props = schema.get("properties", {}).get("params", {}).get("properties", {})
                    field_spec = params_props.get(field_name) or schema.get("properties", {}).get(field_name)
                    if field_spec and "enum" in field_spec:
                        candidates = field_spec["enum"]
        
        # 3. 텍스트 필터링
        if text and candidates:
            clean_text = text.lower().replace("번", "").replace("째", "").strip()
            keywords = {"보고서": "report", "정산": "settlement", "대시보드": "dashboard", "공지": "notice", "세금": "tax", "인버터": "inverter", "펌프": "pump"}
            search_terms = [clean_text]
            for k, v in keywords.items():
                if k in clean_text: search_terms.append(v)
            
            filtered = [c for c in candidates if any(term in c.lower() for term in search_terms) or any(c.lower() in term for term in search_terms)]
            if filtered: return filtered
            elif strict_filter: return []
                
        return candidates

action_manager = ActionManager()
