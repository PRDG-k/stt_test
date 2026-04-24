import json
import re
import os
from functools import lru_cache
from typing import List, Optional, Dict, Any
from app.core.config import settings, vllm_client
from app.services.action_manager import action_manager

# 프롬프트 경로 설정
ACTION_SELECT_PROMPT = 'app/core/prompts/action_selection.md'
PARAM_EXTRACT_PROMPT = 'app/core/prompts/parameter_extraction.md'

# 파일 로드 도우미 (캐싱 적용)
@lru_cache(maxsize=10)
def load_resource(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

async def _call_vllm(prompt: str) -> Optional[Dict[str, Any]]:
    try:
        response = vllm_client.chat.completions.create(
            model=settings.VLLM_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000
        )
        raw_content = response.choices[0].message.content.strip()
        print(f"[NLU DEBUG] Raw Content: {repr(raw_content)}")
        
        json_match = re.search(r'(\{.*\})', raw_content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
            return json.loads(json_str)
    except Exception as e:
        print(f"[VLLM Error] {e}")
    return None

async def _extract_params(action_name: str, text: str, dynamic_context: str, current_action_obj: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    from jinja2 import Template
    schema = action_manager.load_schema(action_name)
    if not schema:
        return None
        
    properties = schema.get("properties", {})
    args_schema = {}
    
    # 1. 스키마 분석 및 평탄화 (LLM 추출용)
    # params 객체가 있으면 내부 속성들을 추출 대상(args_schema)으로 올림
    for prop, spec in properties.items():
        if prop == "action": continue
        
        if prop == "params" and spec.get("type") == "object":
            inner_props = spec.get("properties", {})
            for i_prop, i_spec in inner_props.items():
                args_schema[i_prop] = i_spec
        else:
            args_schema[prop] = spec

    # 2. 기존 데이터 평탄화 (프롬프트 주입용)
    flat_current_params = {}
    if current_action_obj:
        for k, v in current_action_obj.items():
            if k == "params" and isinstance(v, dict):
                flat_current_params.update(v)
            elif k != "action" and k != "requires_confirmation":
                flat_current_params[k] = v

    # 3. LLM 호출을 위한 프롬프트 구성
    template_str = load_resource(PARAM_EXTRACT_PROMPT)
    prompt = Template(template_str).render(
        params_schema=json.dumps(args_schema, indent=2, ensure_ascii=False),
        dynamic_context=dynamic_context,
        action_name=action_name,
        text=text,
        current_params=json.dumps(flat_current_params, indent=2, ensure_ascii=False)
    )
    
    print(f"[NLU DEBUG] Parameter Extraction Prompt for {action_name}")
    
    extracted_args = await _call_vllm(prompt)
    
    # 추출 실패 시에도 기존 데이터를 바탕으로 구조는 생성 (이후 workflow에서 null 처리)
    extracted_args = extracted_args or {}

    # 4. 결과 재구조화 (스키마 형식에 맞게 중첩 구조 복원)
    full_action = {"action": action_name, "requires_confirmation": True, "params": {}}
    
    # 기본값/상수 처리 및 추출된 값 병합
    all_flat = flat_current_params.copy()
    all_flat.update(extracted_args)

    for prop, spec in properties.items():
        if prop == "action": continue
        
        if prop == "params" and spec.get("type") == "object":
            inner_props = spec.get("properties", {})
            required_params = spec.get("required", [])
            for i_prop, i_spec in inner_props.items():
                # 추출된 값이 있으면 사용, 없으면 스키마 기본값 확인
                val = all_flat.get(i_prop)
                if val is None:
                    if "const" in i_spec: val = i_spec["const"]
                    elif "enum" in i_spec and len(i_spec["enum"]) == 1: val = i_spec["enum"][0]
                    elif "default" in i_spec: val = i_spec["default"]
                    # 필수값인데 여전히 없으면 None(null)으로 명시적 설정
                    elif i_prop in required_params: val = None
                
                full_action["params"][i_prop] = val
        else:
            # 루트 레벨 속성
            val = all_flat.get(prop)
            if val is None:
                if "const" in spec: val = spec["const"]
                elif "enum" in spec and len(spec["enum"]) == 1: val = spec["enum"][0]
                elif "default" in spec: val = spec["default"]
                elif prop in schema.get("required", []): val = None
            
            full_action[prop] = val
                
    return full_action
