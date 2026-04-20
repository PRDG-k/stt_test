import json
import re
import os
from functools import lru_cache
from jinja2 import Template
from app.core.config import settings, vllm_client
from app.models.schemas import NLUResponse
from typing import List, Optional, Dict, Any

# 파일 로드 도우미 (캐싱 적용)
@lru_cache(maxsize=10)
def load_resource(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

# 액션 스키마 로드 (캐싱 적용)
@lru_cache(maxsize=1)
def load_action_schemas() -> str:
    schema_dir = 'action-definition/schemas'
    schemas = []
    if os.path.exists(schema_dir):
        # 파일 목록을 정렬하여 캐시 일관성 유지
        filenames = sorted(os.listdir(schema_dir))
        for filename in filenames:
            if filename.endswith('.json'):
                path = os.path.join(schema_dir, filename)
                schemas.append(load_resource(path))
    return "\n---\n".join(schemas)

async def parse_intent(text: str, history: str = "No previous history.") -> NLUResponse:
    # 1. 스키마 동적 로드 (캐시된 결과 반환)
    action_schemas = load_action_schemas()
    
    # 2. 프롬프트 템플릿 로드 (캐시된 결과 반환)
    prompt_template_str = load_resource('app/core/prompts/system_prompt.md')
    
    # 3. 프롬프트 렌더링
    template = Template(prompt_template_str)
    prompt = template.render(
        tools_yaml=action_schemas,
        history=history,
        text=text
    )

    # 4. vLLM 기반 분석 (중앙화된 vllm_client 사용)
    try:
        response = vllm_client.chat.completions.create(
            model=settings.VLLM_MODEL_NAME,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=1000
        )
        
        raw_content = response.choices[0].message.content.strip()
        print(f"[NLU DEBUG] Raw Content: {repr(raw_content)}")

        # JSON 추출
        json_match = re.search(r'(\{.*\})', raw_content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
            
            data = json.loads(json_str)
            
            return NLUResponse(
                transcript=text,
                message=data.get("message", "이해했습니다."),
                candidates=data.get("candidates", []),
                requires_confirmation=data.get("requires_confirmation", True),
                session_id="placeholder"
            )
            
    except Exception as e:
        print(f"[NLU ERROR] {e}")
        return NLUResponse(
            transcript=text,
            message=f"명령 분석 중 오류가 발생했습니다: {str(e)}",
            candidates=[],
            requires_confirmation=False,
            session_id="placeholder"
        )

    return NLUResponse(
        transcript=text,
        message="명령을 이해하지 못했습니다. 다시 말씀해 주세요.",
        candidates=[],
        requires_confirmation=False,
        session_id="placeholder"
    )
